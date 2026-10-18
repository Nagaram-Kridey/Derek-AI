"""Bounded voice sessions. Raw audio stays in memory; stale results are ignored."""

from contextlib import suppress
from datetime import datetime, timezone
import queue
import os
import re
import threading
import time

from .client import APIClient, ClientError, TurnInterrupted
from .desktop_state import desktop_unlocked
from .journal import WorkerLock
from .speech import speak
from .voice_audio import Microphone, UtteranceDetector

YES = {"yes", "confirm", "yes please", "confirm please"}
NO = {"no", "cancel", "no thanks", "cancel that"}
STOP = {"stop", "stop speaking", "stop listening"}


def _console(lines):
    while True:
        try:
            lines.put(input().strip())
        except (EOFError, KeyboardInterrupt):
            lines.put("q")
            return


def _short_reply(text):
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    plain = re.sub(r"[*#`]", "", plain).strip()
    brief = " ".join(re.split(r"(?<=[.!?])\s+", plain)[:2])
    if len(brief) > 1000:
        return brief[:950].rsplit(" ", 1)[0] + ". The full reply is on screen."
    return brief + (" The full reply is on screen." if len(brief) < len(plain) else "")


class VoiceSession:
    def __init__(
        self,
        config,
        model,
        manual=False,
        client=None,
        speech=None,
        output=None,
        console=True,
    ):
        self.config, self.model = config, model
        self.client = client or APIClient(config)
        self.speech = speech or speak
        self.output = output or print
        self.console = console
        self.client.load_voice_state()
        self.microphone = Microphone(config)
        self.detector = UtteranceDetector(config, manual=manual)
        self.lines, self.results = queue.Queue(), queue.Queue()
        self.transcription_lock = threading.Lock()
        self.transcription_busy = threading.Event()
        self.generation, self.stop = 0, threading.Event()
        self.active, self.phase = False, "idle"
        self.deadline = self.last_activity = 0
        self.proposal = self.reading_proposal = None
        self.control_busy = False
        self.quitting = False
        self.last_lock_check = self.turn_started = 0
        self.last_runtime_check = 0

    def job(self, kind, function):
        generation = self.generation

        def run():
            try:
                self.results.put((generation, kind, function(), None))
            except Exception as exc:
                self.results.put((generation, kind, None, exc))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def fresh_generation(self):
        self.stop.set()
        self.generation += 1
        self.stop = threading.Event()

    def listen(self):
        if not self.active or self.control_busy or self.client.pending_turn:
            self.phase = "idle"
            return
        self.detector.reset()
        self.microphone.open()
        self.phase = "listening"
        self.last_activity = time.monotonic()
        self.output("Listening. Speak, or /mute to close the microphone.")

    def start(self):
        if self.active:
            self.output(
                "A session is already active. Use /mute or Enter to interrupt it."
            )
            return
        if not desktop_unlocked():
            self.output("Unlock Windows before starting a voice session.")
            return
        if self.control_busy or self.client.pending_turn:
            self.output(
                "An earlier request is unresolved. Use /retry to read it or /stop to cancel it."
            )
            return
        self.active = True
        self.deadline = time.monotonic() + self.config.voice_session_seconds
        self.fresh_generation()
        self.listen()

    def interrupt(self, *, idle=False, keep_capture=False):
        """Stop audio now; resolve the command before another dispatch."""
        self.fresh_generation()
        if not keep_capture:
            self.microphone.close()
            self.detector.reset()
        self.active = self.active and not idle
        self.phase = "recording" if keep_capture else "idle"
        proposals = [p for p in (self.proposal, self.reading_proposal) if p]
        self.proposal = self.reading_proposal = None
        if not self.control_busy and (self.client.pending_turn or proposals):
            self.control_busy = True

            def resolve():
                result = self.client.cancel_turn()
                for proposal in proposals:
                    self.client.decide_proposal(proposal, False)
                return result

            self.job("control", resolve)
        elif not idle and not keep_capture and not self.control_busy:
            self.listen()

    def capture(self, audio):
        self.microphone.close()
        self.detector.reset()
        if not audio:
            self.output("No clear speech detected.")
            self.listen()
            return
        if self.transcription_busy.is_set():
            self.output(
                "The interrupted transcription is still finishing. Please wait briefly and repeat."
            )
            self.listen()
            return
        self.phase = "transcribing"
        self.turn_started = time.monotonic()
        self.transcription_busy.set()
        stop = self.stop

        def transcribe():
            import numpy as np

            try:
                with self.transcription_lock:
                    if stop.is_set():
                        raise TurnInterrupted("Transcription interrupted.")
                    started = time.monotonic()
                    samples = (
                        np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768
                    )
                    segments, _ = self.model.transcribe(
                        samples,
                        language="en",
                        beam_size=1,
                        vad_filter=True,
                        condition_on_previous_text=False,
                    )
                    text = " ".join(
                        segment.text.strip() for segment in segments
                    ).strip()
                    return text, time.monotonic() - started
            finally:
                self.transcription_busy.clear()

        self.job("transcript", transcribe)

    def dispatch(self, text):
        control = re.sub(r"[^a-z ]", "", text.casefold()).strip()
        if control in STOP:
            self.interrupt(idle=True)
            self.output("Stopped. Microphone closed. Enter starts another session.")
            return
        if self.control_busy or self.client.pending_turn:
            self.output(
                "The previous command is unresolved. Use /retry or /stop, then repeat this request."
            )
            self.microphone.close()
            self.phase = "idle"
            return
        if self.proposal and control in YES | NO:
            proposal, self.proposal = self.proposal, None
            if datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(
                timezone.utc
            ):
                self.output(
                    "That readback expired. Ask again for a fresh proposal, or use the dashboard."
                )
                self.listen()
                return
            self.phase = "confirming"
            self.control_busy = True
            self.job(
                "decision",
                lambda: self.client.decide_proposal(proposal, control in YES),
            )
            return
        self.proposal = None
        if control in YES | NO:
            self.output(
                "No complete readback is armed. Ask for the change again or use its dashboard card."
            )
            self.listen()
            return
        self.phase = "thinking"
        stop = self.stop
        self.job("answer", lambda: self.client.turn(text, stop))

    def answer(self, value):
        reply = value.get(
            "reply_text", value.get("message", "No reply is available. Check Activity.")
        )
        self.output("Derek:", reply)
        proposals = [
            p for p in value.get("action_proposals", []) if p.get("status") == "pending"
        ]
        if len(proposals) == 1:
            self.reading_proposal = proposals[0]
            spoken = (
                proposals[0]["readback"]
                + " Say confirm to apply this exact change, or cancel."
            )
        elif proposals:
            self.output(
                "Several changes need review. Confirm them separately in the dashboard."
            )
            spoken = "Several changes need review. Please use their separate confirmation cards in the dashboard."
        else:
            spoken = _short_reply(reply)
        self.phase = "speaking"
        if self.config.voice_barge_in and self.active:
            self.detector.reset()
            self.microphone.open()
        stop = self.stop
        started, generation = self.turn_started, self.generation

        def first_audio():
            self.results.put(
                (generation, "first_audio", time.monotonic() - started, None)
            )

        self.job("speech", lambda: self.speech(spoken, self.config, stop, first_audio))

    def result(self, item):
        generation, kind, value, error = item
        if kind in {"control", "decision"}:
            # A confirmation may already have committed when interrupted.
            self.control_busy = False
            if error:
                self.output(
                    "Command outcome unavailable. Check Activity before trying the action again."
                )
                self.active = False
                self.microphone.close()
                self.phase = "idle"
            else:
                self.output(value.get("message", "Request resolved."))
                if kind == "decision" and generation == self.generation and self.active:
                    self.answer(value)
                elif self.active and self.phase not in {"recording", "transcribing"}:
                    self.listen()
            return
        if generation != self.generation:
            if kind == "answer" and value:
                for proposal in value.get("action_proposals", []):
                    if proposal.get("status") == "pending":
                        self.job(
                            "discard",
                            lambda p=proposal: self.client.decide_proposal(p, False),
                        )
            return
        if kind == "discard":
            if error:
                self.output(
                    "Interrupted proposal needs review in the dashboard; voice confirmation is disarmed."
                )
            return
        if error:
            if kind == "speech":
                self.output(
                    "Voice playback unavailable or incomplete. Full reply is above; use the dashboard for confirmation."
                )
                self.interrupt()
            elif isinstance(error, TurnInterrupted):
                self.interrupt(idle=True)
            else:
                self.output(
                    "Derek couldn't finish:",
                    str(error)
                    if isinstance(error, ClientError)
                    else "The audio or transcription device is unavailable.",
                )
                if self.client.pending_turn:
                    self.output(
                        "Use /retry to retrieve the saved command; /stop cancels it. It will not be resent automatically."
                    )
                    self.active = False
                    self.phase = "idle"
                else:
                    self.listen()
            return
        if kind == "transcript":
            text, duration = value
            self.output(f"Speech recognition: {duration:.2f}s")
            if not text:
                self.output("No clear words detected.")
                self.listen()
            else:
                self.output("You:", text)
                self.dispatch(text)
        elif kind == "answer":
            self.output(
                f"Command response: {time.monotonic() - self.turn_started:.2f}s since speech ended"
            )
            self.answer(value)
        elif kind == "first_audio":
            self.output(f"First reply audio: {value:.2f}s since speech ended")
        elif kind == "speech":
            self.microphone.close()
            if value.completed and self.reading_proposal:
                self.proposal, self.reading_proposal = self.reading_proposal, None
                self.output(
                    "Readback complete. Say confirm or cancel; confirmation expires after two minutes."
                )
            elif self.reading_proposal:
                self.interrupt()
                return
            if value.first_audio_seconds is not None:
                self.output(
                    f"Speech service to first audio: {value.first_audio_seconds:.2f}s; playback underruns: {value.underruns}"
                )
            self.listen()

    def line(self, line):
        lowered = line.casefold()
        if lowered in {"q", "/quit"}:
            self.interrupt(idle=True)
            self.quitting = True
        elif lowered in {"/mute", "/stop"}:
            self.interrupt(idle=True)
            self.output(
                "Stopped. Microphone closed. Enter starts a new active session."
            )
        elif lowered == "/retry":
            if not desktop_unlocked():
                self.output("Unlock Windows before retrieving a spoken reply.")
                return
            if self.control_busy or self.phase not in {"idle", "listening"}:
                self.output("Stop the active turn first, or wait for it to finish.")
                return
            if not self.client.pending_turn:
                self.output("There is no unresolved request.")
                return
            self.microphone.close()
            self.fresh_generation()
            self.active = True
            self.deadline = time.monotonic() + self.config.voice_session_seconds
            self.turn_started = time.monotonic()
            self.phase = "thinking"
            stop = self.stop
            self.job("answer", lambda: self.client.recover_turn(stop))
        elif lowered == "/new":
            if self.control_busy:
                self.output(
                    "Wait for the current confirmation or cancellation to resolve."
                )
                return
            try:
                self.client.new_conversation()
                self.interrupt(idle=True)
                self.output("New conversation. Enter to start listening.")
            except ClientError as exc:
                self.output(exc)
        elif lowered == "/unmute":
            self.start()
        elif not line:
            if self.phase == "recording":
                self.capture(self.detector.finish().audio)
            elif self.active:
                self.interrupt()
            else:
                self.start()
        else:
            self.output("Use Enter, /mute, /stop, /retry, /new, /unmute or q.")

    def run(self):
        self.output(
            "Enter starts a voice session. Speech ends automatically after a pause."
        )
        self.output(
            "Enter interrupts a reply. /mute closes the microphone; /retry retrieves an unresolved request; /stop cancels; /new resets; q quits."
        )
        if self.config.voice_barge_in:
            self.output(
                "Spoken interruption enabled. Wear headphones; speaker echo is not filtered in this prototype."
            )
        if self.client.pending_turn:
            self.output(
                "An unfinished request was restored. Use /retry or /stop before speaking again."
            )
        if self.console:
            threading.Thread(target=_console, args=(self.lines,), daemon=True).start()
        try:
            while not self.quitting:
                try:
                    self.iterate()
                except Exception:
                    self.interrupt(idle=True)
                    self.output(
                        "Voice paused because the audio device or session is unavailable. Enter to retry; check Activity for unfinished actions."
                    )
                time.sleep(0.01)
        except KeyboardInterrupt:
            self.interrupt(idle=True)
        finally:
            self.stop.set()
            self.microphone.close()
            until = time.monotonic() + 11
            while self.control_busy and time.monotonic() < until:
                with suppress(queue.Empty):
                    self.result(self.results.get(timeout=0.1))
            self.output("Voice closed. Uncertain actions remain visible in Activity.")

    def iterate(self):
        now = time.monotonic()
        if (
            os.getenv("DEREK_MANAGED_RUNTIME") == "true"
            and now - self.last_runtime_check >= 1
        ):
            self.last_runtime_check = now
            from desktop.state import read_record

            if read_record("supervisor").get("stopping"):
                self.line("q")
                return
        if self.active and now - self.last_lock_check >= 1:
            self.last_lock_check = now
            if not desktop_unlocked():
                self.interrupt(idle=True)
                self.output(
                    "Windows locked. Microphone closed. Resume explicitly after unlocking."
                )
        if self.active and (
            now >= self.deadline
            or (
                self.phase == "listening"
                and now - self.last_activity > self.config.voice_idle_seconds
            )
        ):
            self.interrupt(idle=True)
            self.output("Voice session ended. Microphone closed. Enter to resume.")
        with suppress(queue.Empty):
            self.line(self.lines.get_nowait())
        with suppress(queue.Empty):
            self.result(self.results.get_nowait())
        if self.microphone.stream is not None:
            frame = self.microphone.read()
            if frame:
                detected = self.detector.push(frame)
                if detected.started:
                    if self.phase == "speaking":
                        self.interrupt(keep_capture=True)
                    self.phase = "recording"
                    self.output("Recording. Pause to finish, or press Enter.")
                if detected.ended:
                    self.capture(detected.audio)


def voice_loop(config, manual=False):
    try:
        import sounddevice  # noqa: F401
        import webrtcvad  # noqa: F401
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Install companion/requirements.txt to enable voice."
        ) from exc
    with (
        WorkerLock(config.state_dir / "audio-session"),
        WorkerLock(config.state_dir / "voice"),
    ):
        print(
            "Warming speech recognition. The microphone is closed until you press Enter."
        )
        model = WhisperModel(config.whisper_model, device="cpu", compute_type="int8")
        VoiceSession(config, model, manual=manual).run()
