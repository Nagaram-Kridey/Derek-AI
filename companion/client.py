"""Outbound API client; device credentials never authenticate dashboard turns."""

import json
import uuid
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ClientError(RuntimeError):
    pass


class TurnInterrupted(ClientError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class APIClient:
    def __init__(self, config, opener=None):
        self.config = config
        self.opener = opener or build_opener(NoRedirects())
        self.conversation_id = None
        self.pending_turn = None
        self.pending_command_id = None
        self._state_lock = threading.RLock()
        self._voice_store = None
        self._voice_loaded = False

    def post(self, path, payload, *, user=False):
        return self.request("POST", path, payload, user=user)

    def get(self, path, *, user=False):
        return self.request("GET", path, user=user)

    def request(self, method, path, payload=None, *, user=False):
        if not path.startswith("/v1/") or ".." in path or "?" in path:
            raise ValueError("Invalid API endpoint.")
        token = self.config.user_token if user else self.config.device_token
        if user:
            try:
                from desktop.credentials import read_owner_token
                token = read_owner_token(self.config.api_url) or token
            except ImportError:
                pass
        if not token:
            raise ClientError("Sign in to the local workspace to enable online voice, or configure the separate client's user token. Pair a device credential for the browser/file worker.")
        request = Request(self.config.api_url + path, json.dumps(payload).encode("utf-8") if payload is not None else None, {"Authorization": ("Token " if user else "Device ") + token, "Content-Type": "application/json", "Accept": "application/json"}, method=method)
        try:
            with self.opener.open(request, timeout=10 if user else 30) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ClientError("API response is too large.")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ClientError("API returned an invalid response.")
            return result
        except HTTPError as exc:
            # Never log response bodies, full URLs, or authorization headers.
            if user and exc.code in {401, 403}:
                raise ClientError("Online voice access expired. Sign in to the local workspace, then retrieve or stop the saved request. Private local voice is separate.") from None
            if exc.code == 429:
                raise ClientError("The service asked this client to wait. Retrieve the saved request after a short pause; do not repeat the command.") from None
            raise ClientError(f"API returned HTTP {exc.code}.") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ClientError("API connection failed or returned invalid JSON.") from None

    def claim(self):
        return self.post("/v1/desktop/jobs/claim/", {}).get("job")

    def heartbeat(self):
        return self.post("/v1/desktop/heartbeat/", {"version": "0.1.0"})

    def complete(self, job, outcome):
        identifier = str(job["id"])
        if not identifier or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in identifier):
            raise ClientError("Invalid job identifier.")
        return self.post(f"/v1/desktop/jobs/{identifier}/complete/", {"lease_token": job["lease_token"], **outcome})

    def load_voice_state(self):
        with self._state_lock:
            if self._voice_loaded:
                return
            from .voice_state import VoiceState
            self._voice_store = VoiceState(self.config)
            state = self._voice_store.load()
            self.conversation_id = state.get("conversation_id")
            if state.get("request_id"):
                self.pending_turn = {"request_id": state["request_id"]}
                self.pending_command_id = state.get("command_id")
            self._voice_loaded = True

    def _save_voice_state(self):
        if self._voice_store:
            self._voice_store.save(self.conversation_id, self.pending_turn.get("request_id") if self.pending_turn else None, self.pending_command_id)

    def turn(self, text, stop=None):
        self.load_voice_state()
        with self._state_lock:
            if stop and stop.is_set():
                raise TurnInterrupted("Voice turn interrupted before submission.")
            if self.pending_turn:
                raise ClientError("A prior request is unresolved. Use /retry to retrieve it or /stop to cancel it first.")
            payload = {"text": text, "request_id": str(uuid.uuid4()), "input_mode": "voice"}
            if self.conversation_id:
                payload["conversation_id"] = self.conversation_id
            self.pending_turn = payload
            self.pending_command_id = None
            self._save_voice_state()
        result = self.post("/v1/commands/", payload, user=True)
        return self._wait(result, payload["request_id"], stop)

    def recover_turn(self, stop=None):
        self.load_voice_state()
        with self._state_lock:
            if not self.pending_turn:
                raise ClientError("There is no unresolved request.")
            request_id = self.pending_turn["request_id"]
        # A recovery reads saved state. It never resubmits a potentially lost command.
        result = self.get(f"/v1/commands/by-request/{request_id}/", user=True)
        return self._wait(result, request_id, stop)

    def _wait(self, result, request_id, stop):
        deadline = time.monotonic() + getattr(self.config, "turn_timeout_seconds", 120)
        while True:
            with self._state_lock:
                if not self.pending_turn or self.pending_turn["request_id"] != request_id:
                    raise TurnInterrupted("The previous turn was stopped.")
                command_id = str(uuid.UUID(result["command_id"]))
                self.pending_command_id = command_id
                self.conversation_id = str(uuid.UUID(result["conversation_id"]))
                self._save_voice_state()
            if stop and stop.is_set():
                raise TurnInterrupted("Voice turn interrupted; resolve its saved state with /stop or /retry.")
            if result.get("status") not in {"queued", "running"}:
                with self._state_lock:
                    if not self.pending_turn or self.pending_turn["request_id"] != request_id:
                        raise TurnInterrupted("The previous turn was stopped.")
                    self.pending_turn, self.pending_command_id = None, None
                    self._save_voice_state()
                return result["response"]
            if time.monotonic() >= deadline:
                raise ClientError("Command still running. Use /retry to retrieve it or /stop to cancel it.")
            if stop:
                if stop.wait(1):
                    raise TurnInterrupted("Voice turn interrupted.")
            else:
                time.sleep(1)
            result = self.get(f"/v1/commands/{command_id}/", user=True)

    def cancel_turn(self):
        self.load_voice_state()
        with self._state_lock:
            if not self.pending_turn:
                return {"message": "No unresolved command.", "effects_may_continue": False}
            request_id = self.pending_turn["request_id"]
        result = self.post("/v1/commands/cancel/", {"request_id": request_id}, user=True)
        with self._state_lock:
            if self.pending_turn and self.pending_turn["request_id"] == request_id:
                if result.get("conversation_id"):
                    self.conversation_id = str(uuid.UUID(result["conversation_id"]))
                self.pending_turn, self.pending_command_id = None, None
                self._save_voice_state()
        return result

    def decide_proposal(self, proposal, approve):
        identifier = str(uuid.UUID(proposal["id"]))
        return self.post(f"/v1/action-proposals/{identifier}/{'confirm' if approve else 'cancel'}/", {"revision": proposal["revision"], "payload_digest": proposal["payload_digest"]}, user=True)

    def new_conversation(self):
        self.load_voice_state()
        with self._state_lock:
            if self.pending_turn:
                raise ClientError("Resolve the previous request with /stop or /retry first.")
            self.conversation_id = None
            self._save_voice_state()
