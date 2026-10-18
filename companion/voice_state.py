"""Only opaque conversation/request IDs are saved; never audio, text or tokens."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid


class VoiceState:
    def __init__(self, config):
        self.path = Path(config.state_dir) / "voice-state.json"
        self.binding = hashlib.sha256(
            (config.api_url + "\0" + config.user_token).encode()
        ).hexdigest()

    def load(self):
        try:
            if self.path.stat().st_size > 8192:
                return {}
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state, dict) or state.get("binding") != self.binding:
                return {}
            for key in ("conversation_id", "request_id", "command_id"):
                if state.get(key) is not None:
                    state[key] = str(uuid.UUID(state[key]))
            return state
        except (OSError, ValueError, TypeError, AttributeError):
            return {}

    def save(self, conversation_id, request_id=None, command_id=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix="voice-state-", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    {
                        "binding": self.binding,
                        "conversation_id": conversation_id,
                        "request_id": request_id,
                        "command_id": command_id,
                    },
                    stream,
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
