"""One identity boundary for authenticated webhook and local polling updates."""

from django.conf import settings
from . import models as m


def accepted_payload(update):
    if (
        not isinstance(update, dict)
        or type(update.get("update_id")) is not int
        or update["update_id"] < 0
    ):
        return None
    callback = update.get("callback_query")
    message = (
        callback.get("message", {})
        if isinstance(callback, dict)
        else update.get("message", {})
    )
    sender = (
        callback.get("from", {})
        if isinstance(callback, dict)
        else message.get("from", {})
        if isinstance(message, dict)
        else {}
    )
    chat = message.get("chat", {}) if isinstance(message, dict) else {}
    if (
        not isinstance(sender, dict)
        or not isinstance(chat, dict)
        or not settings.TELEGRAM_CHAT_ID
        or str(chat.get("id")) != settings.TELEGRAM_CHAT_ID
        or chat.get("type") != "private"
        or str(sender.get("id")) != settings.TELEGRAM_USER_ID
        or sender.get("is_bot") is not False
    ):
        return None
    if isinstance(callback, dict):
        if (
            not isinstance(callback.get("data"), str)
            or len(callback["data"]) > 64
            or not isinstance(callback.get("id"), str)
            or len(callback["id"]) > 200
        ):
            return None
        return {
            "callback_query": {
                "id": callback["id"],
                "data": callback["data"],
                "chat_id": str(chat["id"]),
                "message_id": message.get("message_id"),
            }
        }
    text, voice = message.get("text"), message.get("voice")
    if isinstance(text, str) and 1 <= len(text) <= 12000:
        return {"message": {"text": text, "chat": {"id": str(chat["id"])}}}
    if (
        isinstance(voice, dict)
        and isinstance(voice.get("file_id"), str)
        and len(voice["file_id"]) <= 512
        and type(voice.get("duration")) is int
        and 0 < voice["duration"] <= 120
        and type(voice.get("file_size", 0)) is int
        and voice.get("file_size", 0) <= 20_000_000
    ):
        return {
            "message": {
                "voice": {"file_id": voice["file_id"]},
                "chat": {"id": str(chat["id"])},
            }
        }
    return None


def store_update(update):
    payload = accepted_payload(update)
    if payload is None:
        return None, False
    return m.TelegramUpdate.objects.get_or_create(
        update_id=update["update_id"], defaults={"payload": payload}
    )
