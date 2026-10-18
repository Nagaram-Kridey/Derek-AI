"""Installed Windows speech only. No Cartesia, upload or cloud fallback."""

import os
import threading
import time
from .speech import SpeechError, SpeechResult


def windows_speak(text, config, stop=None, on_first_audio=None):
    if os.name != "nt":
        raise SpeechError(
            "An installed Windows speech voice is required. The reply remains in text."
        )
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise SpeechError(
            "Install desktop requirements to enable Windows speech. The reply remains in text."
        ) from None
    stop = stop or threading.Event()
    pythoncom.CoInitialize()
    voice = None
    started = time.monotonic()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        if voice.GetVoices().Count == 0:
            raise SpeechError("No installed Windows speech voice is available.")
        if stop.is_set():
            return SpeechResult(False, None, 0, 0)
        voice.Speak(text[:5000], 17)  # SVSFlagsAsync | SVSFIsNotXML.
        while not voice.WaitUntilDone(20):
            if stop.is_set():
                voice.Speak("", 3)  # Purge queued speech.
                return SpeechResult(False, None, 0, 0)
            if time.monotonic() - started > 180:
                voice.Speak("", 3)
                raise SpeechError("Windows speech exceeded its time limit.")
        # SAPI start is not an audio-device measurement; don't report a made-up
        # Cartesia first-audio metric for this backend.
        return SpeechResult(not stop.is_set(), None, time.monotonic() - started, 0)
    finally:
        voice = None
        pythoncom.CoUninitialize()
