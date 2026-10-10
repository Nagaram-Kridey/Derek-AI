"""Outbound API client; device credentials never authenticate dashboard turns."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ClientError(RuntimeError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class APIClient:
    def __init__(self, config, opener=None):
        self.config = config
        self.opener = opener or build_opener(NoRedirects())

    def post(self, path, payload, *, user=False):
        if not path.startswith("/v1/") or ".." in path or "?" in path:
            raise ValueError("Invalid API endpoint.")
        token = self.config.user_token if user else self.config.device_token
        if not token:
            raise ClientError("Set LILYLEO_USER_TOKEN for voice or LILYLEO_DEVICE_TOKEN for the worker.")
        request = Request(self.config.api_url + path, json.dumps(payload).encode("utf-8"), {"Authorization": ("Token " if user else "Device ") + token, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            with self.opener.open(request, timeout=120 if user else 30) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ClientError("API response is too large.")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ClientError("API returned an invalid response.")
            return result
        except HTTPError as exc:
            # Never log response bodies, full URLs, or authorization headers.
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

    def turn(self, text):
        return self.post("/v1/turn", {"text": text}, user=True)
