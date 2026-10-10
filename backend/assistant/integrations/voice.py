"""Optional faster-whisper transcription and Cartesia HTTPS WAV synthesis.

Cartesia bytes contract: https://docs.cartesia.ai/api-reference/tts/bytes,
API version 2026-08-14, model sonic-3.6 (both configurable). Voice IDs must come
from the user's Cartesia account. Model downloads/transcription run only when
the optional faster-whisper extra is explicitly installed and invoked.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path

from .errors import ConfigError, ProviderError


@lru_cache(maxsize=2)
def _whisper(model):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ConfigError("Install the voice extra (faster-whisper) to transcribe audio.") from exc
    if model not in {"tiny", "base", "small", "medium", "large-v3", "turbo", "tiny.en", "base.en", "small.en"}:
        raise ConfigError("Choose a supported WHISPER_MODEL size.")
    return WhisperModel(model, device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))


def transcribe_audio(path, model="base") -> str:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError("Audio must exist and be at most 20 MB.")
    try:
        segments, info = _whisper(model).transcribe(str(path), beam_size=3, language="en", vad_filter=True)
        if info.duration > 300:
            raise ValueError("Audio must be at most five minutes long.")
        text = " ".join(segment.text.strip() for segment in segments).strip()
    except (ConfigError, ValueError):
        raise
    except Exception as exc:
        raise ProviderError("Audio transcription failed. Check the audio format and voice installation.") from exc
    if not text:
        raise ValueError("No speech was detected in the audio.")
    return text[:20000]


def synthesize_speech(text: str, api_key: str, voice_id: str) -> bytes:
    import httpx

    if not api_key or not voice_id:
        raise ConfigError("Set CARTESIA_API_KEY and CARTESIA_VOICE_ID to enable speech output.")
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise ValueError("Speech text must contain 1 to 5000 characters.")
    payload = {"model_id": os.getenv("CARTESIA_MODEL", "sonic-3.6"), "transcript": text, "voice": voice_id,
               "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}, "language": "en"}
    headers = {"Authorization": f"Bearer {api_key}", "Cartesia-Version": os.getenv("CARTESIA_API_VERSION", "2026-08-14")}
    body = bytearray()
    deadline = time.monotonic() + 60
    try:
        with httpx.stream("POST", "https://api.cartesia.ai/tts/bytes", headers=headers, json=payload, timeout=30, follow_redirects=False) as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith(("audio/", "application/octet-stream")):
                raise ProviderError("Cartesia returned an unexpected response type.")
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > 30_000_000 or time.monotonic() > deadline:
                    raise ProviderError("Speech output exceeded the download limit.")
                body.extend(chunk)
    except httpx.HTTPError as exc:
        raise ProviderError("Cartesia speech synthesis failed.") from exc
    if not body.startswith(b"RIFF"):
        raise ProviderError("Cartesia did not return WAV audio.")
    return bytes(body)
