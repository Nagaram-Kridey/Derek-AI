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
    browser_channel: str = "chromium"
    turn_timeout_seconds: int = 120
    voice_silence_ms: int = 900
    voice_idle_seconds: int = 30
    voice_session_seconds: int = 300
    voice_max_utterance_seconds: int = 120
    voice_vad_mode: int = 2
    voice_barge_in: bool = False
    voice_input_device: str | None = None
    voice_output_device: str | None = None

    @property
    def browser_profile(self):
        name = "browser-profile" if self.browser_channel == "chromium" else "browser-profile-" + self.browser_channel
        return self.state_dir / name

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
        browser_channel = os.getenv("LILYLEO_BROWSER_CHANNEL", "chromium").strip().lower()
        if browser_channel not in {"chromium", "chrome", "msedge"}:
            raise ValueError("LILYLEO_BROWSER_CHANNEL must be chromium, chrome, or msedge.")
        default_state = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "LilyLeo"
        token = os.getenv("LILYLEO_USER_TOKEN", "")
        try:
            from desktop.credentials import read_owner_token
            token = read_owner_token(api) or token
        except ImportError:
            pass
        return cls(api_url=api, device_token=os.getenv("LILYLEO_DEVICE_TOKEN", ""), user_token=token,
                   state_dir=Path(os.getenv("LILYLEO_STATE_DIR", str(default_state))).expanduser().resolve(),
                   poll_seconds=max(1, float(os.getenv("LILYLEO_POLL_SECONDS", "5"))), allow_local_http=local,
                   cartesia_key=os.getenv("CARTESIA_API_KEY", ""), cartesia_voice=os.getenv("CARTESIA_VOICE_ID", ""),
                   cartesia_model=os.getenv("CARTESIA_MODEL", "sonic-3.6"), cartesia_version=os.getenv("CARTESIA_API_VERSION", "2026-08-14"),
                   whisper_model=os.getenv("WHISPER_MODEL", "base.en"), browser_channel=browser_channel,
                   turn_timeout_seconds=min(1800, max(30, int(os.getenv("LILYLEO_TURN_TIMEOUT_SECONDS", "120")))),
                   voice_silence_ms=min(3000, max(450, int(os.getenv("DEREK_VOICE_SILENCE_MS", "900")))),
                   voice_idle_seconds=min(120, max(10, int(os.getenv("DEREK_VOICE_IDLE_SECONDS", "30")))),
                   voice_session_seconds=min(1800, max(60, int(os.getenv("DEREK_VOICE_SESSION_SECONDS", "300")))),
                   voice_max_utterance_seconds=min(120, max(5, int(os.getenv("DEREK_VOICE_MAX_UTTERANCE_SECONDS", "120")))),
                   voice_vad_mode=min(3, max(0, int(os.getenv("DEREK_VOICE_VAD_MODE", "2")))),
                   voice_barge_in=os.getenv("DEREK_VOICE_BARGE_IN", "false").lower() == "true",
                   voice_input_device=os.getenv("DEREK_VOICE_INPUT_DEVICE") or None,
                   voice_output_device=os.getenv("DEREK_VOICE_OUTPUT_DEVICE") or None)
