"""Bounded streamed PCM playback; cancellation never waits for an entire WAV."""
from dataclasses import dataclass
from contextlib import suppress
import queue
import threading
import time


class SpeechError(RuntimeError):
    pass


@dataclass
class SpeechResult:
    completed: bool
    first_audio_seconds: float | None
    audio_seconds: float
    underruns: int


def speak(text, config, stop=None, on_first_audio=None):
    import httpx
    import sounddevice as sd
    if not config.cartesia_key or not config.cartesia_voice:
        raise SpeechError("Configure Cartesia to enable voice replies. The full reply remains in text.")
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise SpeechError("Speech text must contain 1-5000 characters.")
    stop = stop or threading.Event()
    chunks = queue.Queue(maxsize=32)
    downloaded = threading.Event()
    drained = threading.Event()
    buffered = bytearray()
    sample_rate = 24000
    started_at = time.monotonic()
    stats = {"first": None, "bytes": 0, "underruns": 0}
    stream = None

    def callback(output, frames, timing, status):
        if stop.is_set():
            raise sd.CallbackAbort
        required = frames * 2
        while len(buffered) < required:
            try:
                buffered.extend(chunks.get_nowait())
            except queue.Empty:
                break
        output[:] = b"\x00" * required
        count = min(required, len(buffered))
        if count:
            output[:count] = buffered[:count]
            del buffered[:count]
            stats["bytes"] += count
            if stats["first"] is None and any(output[:count]):
                stats["first"] = time.monotonic() - started_at
                if on_first_audio:
                    on_first_audio()
        if count < required and not downloaded.is_set():
            stats["underruns"] += 1
        if downloaded.is_set() and not buffered and chunks.empty():
            drained.set()
            raise sd.CallbackStop

    payload = {"model_id": config.cartesia_model, "transcript": text, "voice": config.cartesia_voice,
               "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": sample_rate}, "language": "en"}
    headers = {"Authorization": "Bearer " + config.cartesia_key, "Cartesia-Version": config.cartesia_version}
    total = 0
    tail = b""
    try:
        with httpx.stream("POST", "https://api.cartesia.ai/tts/bytes", headers=headers, json=payload,
                          timeout=httpx.Timeout(10, connect=5), follow_redirects=False) as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith(("audio/", "application/octet-stream")):
                raise SpeechError("The speech service returned an unexpected format.")
            for chunk in response.iter_bytes(chunk_size=960):
                if stop.is_set():
                    break
                total += len(chunk)
                if total > 12_000_000 or time.monotonic() - started_at > 180:
                    raise SpeechError("Speech exceeded its size or time limit.")
                data = tail + chunk
                usable = len(data) - len(data) % 2
                tail = data[usable:]
                if not usable:
                    continue
                while not stop.is_set():
                    try:
                        chunks.put(data[:usable], timeout=0.05)
                        break
                    except queue.Full:
                        if stream is not None and not stream.active:
                            raise SpeechError("The audio device stopped during playback.")
                if stream is None and not stop.is_set():
                    device = config.voice_output_device
                    device = int(device) if device and device.isdigit() else device
                    stream = sd.RawOutputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=480,
                                                latency="low", device=device, callback=callback)
                    stream.start()
        downloaded.set()
        if tail and not stop.is_set():
            raise SpeechError("The speech stream ended with an incomplete audio sample.")
        if stream is None and not stop.is_set():
            raise SpeechError("The speech service returned no playable audio.")
        while stream is not None and stream.active and not stop.is_set():
            if time.monotonic() - started_at > 180:
                raise SpeechError("Speech playback timed out.")
            stop.wait(0.02)
        return SpeechResult(drained.is_set() and not stop.is_set(), stats["first"], stats["bytes"] / (sample_rate * 2), stats["underruns"])
    except (httpx.HTTPError, OSError):
        if stop.is_set():
            return SpeechResult(False, stats["first"], stats["bytes"] / (sample_rate * 2), stats["underruns"])
        raise SpeechError("Speech playback failed. Check the speech service and selected output device.") from None
    finally:
        downloaded.set()
        if stream is not None:
            with suppress(Exception):
                stream.abort()
            with suppress(Exception):
                stream.close()
