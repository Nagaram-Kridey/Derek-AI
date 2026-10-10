"""Environment configuration; no credentials are written to disk by this module."""

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    api_url: str
    device_token: str
    user_token: str
    state_dir: Path
    poll_seconds: float = 5.0
    allow_local_http: bool = False
    cartesia_key: str = ""
    cartesia_voice: str = ""
    cartesia_model: str = "sonic-3.6"
    cartesia_version: str = "2026-08-14"
    whisper_model: str = "base.en"

    @property
    def browser_profile(self):
        return self.state_dir / "browser-profile"

    @classmethod
    def from_env(cls):
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
        except ImportError:
            pass
        local = os.getenv("LILYLEO_ALLOW_LOCAL_HTTP", "false").lower() == "true"
        api = os.getenv("LILYLEO_API_URL", "http://localhost:8000").rstrip("/")
        parsed = urlsplit(api)
        if (parsed.scheme != "https" and not (local and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"})) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("LILYLEO_API_URL requires HTTPS; enable LILYLEO_ALLOW_LOCAL_HTTP only for a loopback development server.")
        if not parsed.hostname:
            raise ValueError("LILYLEO_API_URL is invalid.")
        default_state = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "LilyLeo"
        return cls(api, os.getenv("LILYLEO_DEVICE_TOKEN", ""), os.getenv("LILYLEO_USER_TOKEN", ""), Path(os.getenv("LILYLEO_STATE_DIR", str(default_state))).expanduser().resolve(), max(1, float(os.getenv("LILYLEO_POLL_SECONDS", "5"))), local, os.getenv("CARTESIA_API_KEY", ""), os.getenv("CARTESIA_VOICE_ID", ""), os.getenv("CARTESIA_MODEL", "sonic-3.6"), os.getenv("CARTESIA_API_VERSION", "2026-08-14"), os.getenv("WHISPER_MODEL", "base.en"))
