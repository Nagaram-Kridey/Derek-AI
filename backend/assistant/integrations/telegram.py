"""Telegram Bot API HTTPS transport; caller must enforce the approved chat ID.

Bot API getFile downloads are bounded below its documented 20 MB cloud limit.
Tokens are never included in exception messages. Redirects are never followed.
https://core.telegram.org/bots/api
"""

from __future__ import annotations

import re
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote

from .errors import ConfigError, ProviderError

MAX_VOICE_BYTES = 20_000_000


def _base(bot_token):
    if not bot_token:
        raise ConfigError("Set TELEGRAM_BOT_TOKEN to enable Telegram.")
    if not isinstance(bot_token, str) or not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", bot_token):
        raise ConfigError("TELEGRAM_BOT_TOKEN is malformed.")
    return f"https://api.telegram.org/bot{bot_token}"


def _call(bot_token, method, **kwargs):
    import httpx

    url = _base(bot_token) + "/" + method
    try:
        response = httpx.post(url, timeout=30, follow_redirects=False, **kwargs)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") is not True:
            raise ProviderError("Telegram rejected the request.")
        return data.get("result")
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("Telegram request failed.") from exc


def _chat_id(chat_id):
    if not re.fullmatch(r"-?[0-9]{1,20}", str(chat_id)):
        raise ValueError("A numeric approved Telegram chat ID is required.")
    return str(chat_id)


def send_message(bot_token: str, chat_id, text: str):
    if not isinstance(text, str) or not text.strip() or len(text) > 16000:
        raise ValueError("Telegram message must contain 1 to 16000 characters.")
    chat_id = _chat_id(chat_id)
    results = []
    for start in range(0, len(text), 4000):
        results.append(_call(bot_token, "sendMessage", json={"chat_id": chat_id, "text": text[start:start + 4000], "link_preview_options": {"is_disabled": True}}))
    return results


def send_document(bot_token: str, chat_id, path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 45_000_000:
        raise ValueError("Telegram document must exist and be at most 45 MB.")
    with path.open("rb") as file:
        return _call(bot_token, "sendDocument", data={"chat_id": _chat_id(chat_id)}, files={"document": (path.name, file)})


def download_voice(bot_token: str, file_id: str, max_bytes=MAX_VOICE_BYTES) -> bytes:
    import httpx

    _base(bot_token)
    if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", file_id):
        raise ValueError("Invalid Telegram file ID.")
    max_bytes = min(max(int(max_bytes), 1), MAX_VOICE_BYTES)
    data = _call(bot_token, "getFile", json={"file_id": file_id})
    if not isinstance(data, dict):
        raise ProviderError("Telegram returned invalid file information.")
    if int(data.get("file_size") or 0) > max_bytes:
        raise ValueError("Telegram voice note exceeds the upload limit.")
    path = data.get("file_path", "")
    decoded = unquote(path)
    if (not path or len(path) > 1024 or path != decoded or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
            or path.startswith("/") or any(part in {".", ".."} for part in path.split("/")) or not PurePosixPath(path).suffix):
        raise ProviderError("Telegram returned an unsafe file path.")
    url = f"https://api.telegram.org/file/bot{bot_token}/{quote(path, safe='/')}"
    body = bytearray()
    deadline = time.monotonic() + 35
    try:
        with httpx.stream("GET", url, timeout=15, follow_redirects=False) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > max_bytes or time.monotonic() > deadline:
                    raise ValueError("Telegram voice note exceeds the download limit.")
                body.extend(chunk)
    except httpx.HTTPError as exc:
        raise ProviderError("Telegram voice download failed.") from exc
    if not body:
        raise ProviderError("Telegram returned an empty voice note.")
    return bytes(body)
