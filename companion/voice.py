"""Push-to-talk audio stays local until its transcript is sent to the turn API."""
import io
import os
import tempfile
import threading
import wave
from .client import APIClient, ClientError

def speak(text, config):
    if not config.cartesia_key or not config.cartesia_voice:
        return
    import httpx
    import sounddevice as sd
    import numpy as np
    response = httpx.post("https://api.cartesia.ai/tts/bytes", headers={"Authorization": "Bearer " + config.cartesia_key, "Cartesia-Version": config.cartesia_version}, json={"model_id": config.cartesia_model, "transcript": text[:5000], "voice": config.cartesia_voice, "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}, "language": "en"}, timeout=60, follow_redirects=False)
    response.raise_for_status()
    if len(response.content) > 30_000_000 or not response.content.startswith(b"RIFF"):
        raise ValueError("Invalid or oversized speech audio")
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        if audio.getsampwidth() != 2:
            raise ValueError("Unexpected speech audio format")
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16).reshape(-1, audio.getnchannels())
        sd.play(samples, audio.getframerate())
        sd.wait()

def voice_loop(config):
    try:
        import sounddevice as sd
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install companion/requirements.txt to enable voice") from exc
    model = WhisperModel(config.whisper_model, device="cpu", compute_type="int8")
    client = APIClient(config)
    print("Press Enter to record, Enter again to stop (maximum 120 seconds). Type q to leave.")
    while input("Ready > ").strip().lower() != "q":
        chunks = []
        done = threading.Event()
        def callback(audio, frames, timing, status):
            if not done.is_set() and sum(len(chunk) for chunk in chunks) < 16000 * 120:
                chunks.append(audio.copy())
        with sd.InputStream(samplerate=16000, channels=1, dtype="int16", callback=callback):
            input("Recording. Press Enter to stop > ")
            done.set()
        if not chunks:
            continue
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(np.concatenate(chunks).tobytes())
            segments, _ = model.transcribe(path, language="en", vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments)
            if not text:
                print("No speech detected.")
                continue
            print("You:", text)
            try:
                result = client.turn(text)
            except ClientError as exc:
                print("Derek couldn't answer:", exc)
                print("Check the backend's provider configuration and availability, then try again. The voice client is still ready.")
                continue
            print("Derek:", result["reply_text"])
            try:
                speak(result["reply_text"], config)
            except Exception:
                print("Speech playback unavailable; the text response is shown above.")
        finally:
            os.unlink(path)
