"""Local long polling. Never delete or replace a registered public webhook."""

import os
import signal
import sys
import threading
import time

from .state import ROOT, RUNTIME, write_record, read_record


def main():
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import close_old_connections, transaction
    from assistant import models as m
    from assistant.integrations.telegram import (
        _call,
        TelegramRateLimit,
        TelegramConflict,
    )
    from assistant.telegram_ingress import store_update
    from companion.journal import WorkerLock

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    state = {"status": "starting", "pid": os.getpid(), "mode": "polling"}

    def pause(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until and not stop.is_set():
            if read_record("supervisor").get("stopping"):
                stop.set()
                break
            stop.wait(min(1, max(0, until - time.monotonic())))

    def heartbeat():
        while not stop.is_set():
            try:
                write_record("telegram", dict(state))
            except OSError:
                pass
            stop.wait(5)

    with WorkerLock(RUNTIME / "telegram-lock"):
        threading.Thread(target=heartbeat, daemon=True).start()
        last_webhook_check = 0
        failures = 0
        try:
            while not stop.is_set() and not read_record("supervisor").get("stopping"):
                close_old_connections()
                try:
                    if time.monotonic() - last_webhook_check > 60:
                        webhook = _call(
                            settings.TELEGRAM_BOT_TOKEN, "getWebhookInfo", json={}
                        )
                        last_webhook_check = time.monotonic()
                        if not isinstance(webhook, dict) or webhook.get("url"):
                            state["status"] = "webhook_configured"
                            pause(60)
                            continue
                        state["status"] = "ready"
                    user = get_user_model().objects.get(is_active=True)
                    owner_state, _ = m.AssistantState.objects.get_or_create(user=user)
                    updates = _call(
                        settings.TELEGRAM_BOT_TOKEN,
                        "getUpdates",
                        json={
                            "offset": owner_state.telegram_offset,
                            "timeout": 20,
                            "limit": 50,
                            "allowed_updates": ["message", "callback_query"],
                        },
                    )
                    if not isinstance(updates, list):
                        raise ValueError("Invalid Telegram update list")
                    with transaction.atomic():
                        owner_state = m.AssistantState.objects.select_for_update().get(
                            user=user
                        )
                        offset = owner_state.telegram_offset
                        for update in updates:
                            if (
                                not isinstance(update, dict)
                                or type(update.get("update_id")) is not int
                            ):
                                continue
                            store_update(update)
                            offset = max(offset, update["update_id"] + 1)
                        owner_state.telegram_offset = offset
                        owner_state.save(update_fields=["telegram_offset"])
                    failures = 0
                    state["status"] = "ready"
                except TelegramRateLimit as exc:
                    state["status"] = "rate_limited"
                    pause(exc.retry_after)
                except TelegramConflict:
                    state["status"] = "receiver_conflict"
                    pause(60)
                    last_webhook_check = 0
                except Exception:
                    # Bot tokens are embedded in Telegram URLs. Never log the
                    # request, exception string or provider body.
                    failures += 1
                    state["status"] = "recovering"
                    pause(min(60, 2 ** min(failures, 6)))
        finally:
            stop.set()
            write_record("telegram", {**state, "status": "stopped"})


if __name__ == "__main__":
    main()
