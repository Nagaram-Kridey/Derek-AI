"""Owner-visible local runtime health without environment values or paths."""

from datetime import datetime, timezone
import json
from django.conf import settings

NAMES = {
    "backend": "Assistant service",
    "interactive": "Conversations",
    "research": "Research",
    "delivery": "Reminders and delivery",
    "scheduler": "Scheduler",
    "companion": "Laptop actions",
    "telegram": "Telegram receiver",
}


def runtime_status():
    if not settings.LOCAL_EXECUTION:
        return {
            "mode": "celery",
            "managed": False,
            "services": [],
            "note": "This installation uses separate worker and scheduler services.",
        }
    root = settings.BASE_DIR.parent / ".companion" / "runtime"
    now = datetime.now(timezone.utc)

    def record(name):
        try:
            path = root / (name + ".json")
            if path.stat().st_size > 16000:
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    supervisor = record("supervisor")
    backup = record("backup")
    rows = []
    for name, title in NAMES.items():
        value = record(name)
        try:
            age = (now - datetime.fromisoformat(value["updated_at"])).total_seconds()
            fresh = 0 <= age < 30
        except (TypeError, ValueError, KeyError):
            fresh = False
        rows.append(
            {
                "id": name,
                "title": title,
                "status": value.get("status", "offline") if fresh else "offline",
                "last_seen": value.get("updated_at"),
                "task_started_at": value.get("task_started_at") if fresh else None,
            }
        )
    return {
        "mode": "local",
        "managed": True,
        "stopping": bool(supervisor.get("stopping")),
        "voice_shortcut": supervisor.get("voice_shortcut"),
        "start_at_login": supervisor.get("start_at_login"),
        "backup": {
            key: backup.get(key)
            for key in ("status", "created_at", "encrypted", "bytes", "reason")
        },
        "services": rows,
        "note": "Runs on this laptop without Docker or Redis. Closing the browser leaves the assistant running in the tray.",
    }
