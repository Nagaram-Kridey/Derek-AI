"""Local PCM capture and bounded utterance detection. No audio files or uploads."""

from collections import deque
from dataclasses import dataclass
from contextlib import suppress
import queue
import threading

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


@dataclass
class Detection:
    started: bool = False
    ended: bool = False
    audio: bytes | None = None
    limit_reached: bool = False


class UtteranceDetector:
    def __init__(self, config, manual=False):
        import webrtcvad

        self.vad = webrtcvad.Vad(config.voice_vad_mode)
        self.silence_frames = max(1, config.voice_silence_ms // FRAME_MS)
        self.max_frames = config.voice_max_utterance_seconds * 1000 // FRAME_MS
        self.manual = manual
        self.reset()

    def reset(self):
        self.preroll = deque(maxlen=10)
        self.onset = deque(maxlen=5)
        self.frames = []
        self.voiced_frames = 0
        self.silent_frames = 0
        self.started = False

    def push(self, frame):
        if len(frame) != FRAME_BYTES:
            raise RuntimeError(
                "Unexpected microphone frame size. Select a 16 kHz mono input device."
            )
        voiced = self.vad.is_speech(frame, SAMPLE_RATE)
        if not self.started:
            self.preroll.append(frame)
            self.onset.append(voiced)
            if sum(self.onset) < 3:
                return Detection()
            self.started = True
            self.frames = list(self.preroll)
            self.voiced_frames = sum(self.onset)
            return Detection(started=True)
        self.frames.append(frame)
        self.voiced_frames += int(voiced)
        self.silent_frames = 0 if voiced else self.silent_frames + 1
        limited = len(self.frames) >= self.max_frames
        if limited or (not self.manual and self.silent_frames >= self.silence_frames):
            return self.finish(limited)
        return Detection()

    def finish(self, limited=False):
        audio = b"".join(self.frames) if self.voiced_frames * FRAME_MS >= 300 else None
        self.reset()
        return Detection(ended=True, audio=audio, limit_reached=limited)


class Microphone:
    def __init__(self, config):
        self.config = config
        self.frames = queue.Queue(maxsize=100)
        self.overflow = threading.Event()
        self.stream = None

    def open(self):
        if self.stream is not None:
            return
        import sounddevice as sd

        self.clear()

        def callback(data, count, timing, status):
            if status.input_overflow:
                self.overflow.set()
            try:
                self.frames.put_nowait(bytes(data))
            except queue.Full:
                self.overflow.set()

        device = self.config.voice_input_device
        device = int(device) if device and device.isdigit() else device
        self.stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=FRAME_SAMPLES,
            dtype="int16",
            device=device,
            callback=callback,
        )
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            self.stream = None
            raise

    def read(self):
        if self.overflow.is_set():
            raise RuntimeError(
                "Microphone input overflowed. The incomplete utterance was discarded; please repeat it."
            )
        try:
            return self.frames.get_nowait()
        except queue.Empty:
            return None

    def clear(self):
        self.overflow.clear()
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break

    def close(self):
        if self.stream is not None:
            stream, self.stream = self.stream, None
            with suppress(Exception):
                stream.abort()
            with suppress(Exception):
                stream.close()
        self.clear()
