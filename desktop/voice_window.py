"""Small native voice surface. Tk runs on its main thread; audio never does."""

import argparse
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from companion.config import Config
from companion.journal import WorkerLock
from .state import RUNTIME

COLORS = {"paper": "#f6f7f3", "ink": "#183b36", "muted": "#65776e", "mint": "#d3eadc"}
PHASES = {
    "idle": "Microphone closed",
    "listening": "Listening",
    "recording": "Hearing your request",
    "transcribing": "Turning speech into text",
    "thinking": "Derek is thinking",
    "speaking": "Derek is speaking",
    "confirming": "Saving your confirmed change",
}


def main():
    parser = argparse.ArgumentParser(description="Derek voice window")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    root = tk.Tk()
    root.title("Derek · Private voice" if args.private else "Derek · Voice")
    root.geometry("560x620")
    root.minsize(410, 440)
    root.configure(bg=COLORS["paper"])
    try:
        root.iconbitmap(str(RUNTIME / "derek.ico"))
    except tk.TclError:
        pass
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Derek.TFrame", background=COLORS["paper"])
    style.configure(
        "Derek.TLabel",
        background=COLORS["paper"],
        foreground=COLORS["ink"],
        font=("Segoe UI", 11),
    )
    style.configure(
        "Title.TLabel",
        background=COLORS["paper"],
        foreground=COLORS["ink"],
        font=("Segoe UI", 25, "bold"),
    )
    style.configure(
        "Muted.TLabel",
        background=COLORS["paper"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Listen.TButton",
        font=("Segoe UI", 11, "bold"),
        padding=(18, 10),
        background=COLORS["ink"],
        foreground="white",
    )
    style.map(
        "Listen.TButton",
        background=[("active", "#315d46"), ("disabled", "#d7dfd5")],
        foreground=[("disabled", "#70836f")],
    )
    style.configure("Control.TButton", font=("Segoe UI", 10), padding=(14, 10))
    content = ttk.Frame(root, style="Derek.TFrame", padding=25)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text="PRIVATE · ON THIS LAPTOP" if args.private else "A LITTLE HELP, OUT LOUD",
        style="Muted.TLabel",
    ).pack(anchor="w")
    ttk.Label(content, text="Talk to Derek", style="Title.TLabel").pack(
        anchor="w", pady=(8, 8)
    )
    subtitle = (
        "Local Ollama and an installed Windows voice. No account tools or history sync."
        if args.private
        else "Speak naturally, then pause. Important changes need a complete readback and your confirmation."
    )
    ttk.Label(content, text=subtitle, style="Muted.TLabel", wraplength=490).pack(
        anchor="w"
    )
    state_label = ttk.Label(
        content, text="Preparing voice · microphone closed", style="Derek.TLabel"
    )
    state_label.pack(anchor="w", pady=(24, 14))
    transcript = scrolledtext.ScrolledText(
        content,
        wrap="word",
        state="disabled",
        bg="white",
        fg=COLORS["ink"],
        relief="flat",
        borderwidth=0,
        padx=15,
        pady=15,
        font=("Segoe UI", 10),
        height=13,
    )
    transcript.pack(fill="both", expand=True)
    controls = ttk.Frame(content, style="Derek.TFrame")
    controls.pack(fill="x", pady=(18, 10))
    primary = ttk.Button(
        controls, text="Listen", style="Listen.TButton", state="disabled"
    )
    primary.pack(side="left")
    mute = ttk.Button(controls, text="Mute", style="Control.TButton", state="disabled")
    mute.pack(side="left", padx=8)
    stop_button = ttk.Button(
        controls, text="Stop reply", style="Control.TButton", state="disabled"
    )
    stop_button.pack(side="left")
    extra = ttk.Frame(content, style="Derek.TFrame")
    extra.pack(fill="x", pady=(0, 10))
    retrieve = ttk.Button(
        extra, text="Retrieve saved reply", style="Control.TButton", state="disabled"
    )
    retrieve.pack(side="left")
    new = ttk.Button(
        extra, text="New conversation", style="Control.TButton", state="disabled"
    )
    new.pack(side="right")
    ttk.Label(
        content,
        text="Space: start / finish / interrupt · Esc: mute\nThe microphone closes when idle, muted, locked, or this window exits.",
        style="Muted.TLabel",
        wraplength=490,
    ).pack(anchor="w")
    output = queue.Queue()
    session = [None]
    closing = threading.Event()
    stopped = threading.Event()

    def emit(*parts):
        output.put(" ".join(str(part) for part in parts))

    def command(value):
        if session[0] and not closing.is_set():
            session[0].lines.put(value)

    def close():
        closing.set()
        primary.configure(state="disabled")
        mute.configure(state="disabled")
        stop_button.configure(state="disabled")
        retrieve.configure(state="disabled")
        new.configure(state="disabled")
        state_label.configure(text="Closing microphone and stopping this reply…")
        if session[0]:
            session[0].lines.put("q")
        else:
            root.destroy()  # Model warmup is a daemon; it never opened capture.

    def primary_action():
        current = session[0]
        command("/mute" if current and current.phase == "listening" else "")

    primary.configure(command=primary_action)
    mute.configure(command=lambda: command("/mute"))
    stop_button.configure(command=lambda: command("/stop"))
    retrieve.configure(command=lambda: command("/retry"))
    new.configure(command=lambda: command("/new"))
    root.protocol("WM_DELETE_WINDOW", close)
    root.bind(
        "<space>",
        lambda event: (
            (primary_action(), "break")[1]
            if event.widget is not transcript
            and not isinstance(event.widget, ttk.Button)
            else None
        ),
    )
    root.bind("<Escape>", lambda _: command("/mute"))
    root.bind("<Control-n>", lambda _: command("/new"))

    def worker():
        try:
            config = Config.from_env()
            if not args.private and not config.user_token:
                raise RuntimeError(
                    "Sign in to the local workspace first, then reopen online voice. Private voice does not need this account sign-in."
                )
            with WorkerLock(config.state_dir / "audio-session"):
                from faster_whisper import WhisperModel
                from companion.voice import VoiceSession

                emit(
                    "Warming local speech recognition. Capture stays closed until Listen."
                )
                model = WhisperModel(
                    config.whisper_model, device="cpu", compute_type="int8"
                )
                if closing.is_set():
                    return
                if args.private:
                    from companion.private import PrivateClient
                    from companion.windows_speech import windows_speak

                    with WorkerLock(config.state_dir / "private" / "session-lock"):
                        current = VoiceSession(
                            config,
                            model,
                            client=PrivateClient(config),
                            speech=windows_speak,
                            output=emit,
                            console=False,
                        )
                        session[0] = current
                        current.run()
                else:
                    with WorkerLock(config.state_dir / "voice"):
                        current = VoiceSession(
                            config, model, output=emit, console=False
                        )
                        session[0] = current
                        current.run()
        except RuntimeError as exc:
            emit("Voice setup:", str(exc))
        except Exception:
            emit(
                "Voice is unavailable. Check the audio packages, selected devices and model cache. The microphone is closed."
            )
        finally:
            stopped.set()

    def tick():
        try:
            while True:
                line = output.get_nowait()
                transcript.configure(state="normal")
                transcript.insert("end", line + "\n\n")
                if int(transcript.index("end-1c").split(".")[0]) > 350:
                    transcript.delete("1.0", "60.0")
                transcript.see("end")
                transcript.configure(state="disabled")
        except queue.Empty:
            pass
        if stopped.is_set() and (
            closing.is_set() or (session[0] and session[0].quitting)
        ):
            root.destroy()
            return
        current = session[0]
        if not closing.is_set():
            if stopped.is_set():
                state_label.configure(text="Voice unavailable · microphone closed")
                for control in (primary, mute, stop_button, retrieve, new):
                    control.configure(state="disabled")
            elif current:
                state_label.configure(text=PHASES.get(current.phase, current.phase))
                primary.configure(
                    text="Finish utterance"
                    if current.phase == "recording"
                    else "Interrupt reply"
                    if current.active and current.phase not in {"idle", "listening"}
                    else "Pause listening"
                    if current.phase == "listening"
                    else "Listen",
                    state="normal",
                )
                mute.configure(state="normal")
                stop_button.configure(state="normal")
                retrieve.configure(
                    state="normal"
                    if current.client.pending_turn and current.phase == "idle"
                    else "disabled"
                )
                new.configure(
                    state="normal"
                    if not current.control_busy and not current.client.pending_turn
                    else "disabled"
                )
        root.after(120, tick)

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
