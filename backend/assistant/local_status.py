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
    def record_age(value):
        try:
            return (now - datetime.fromisoformat(value['updated_at'])).total_seconds()
        except (ValueError, KeyError, TypeError):
            return float('inf')
    supervisor_fresh = 0 <= record_age(supervisor) < 30
    backup_status = backup.get('status', 'pending')
    if backup_status == 'ready' and not 0 <= record_age(backup) < 26 * 60 * 60:
        backup_status = 'overdue'
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
        "supervisor_status": supervisor.get('status', 'offline') if supervisor_fresh else 'offline',
        "issues": supervisor.get('issues', {}) if supervisor_fresh else {},
        "stopping": bool(supervisor.get("stopping")) if supervisor_fresh else False,
        "voice_shortcut": supervisor.get("voice_shortcut") if supervisor_fresh else None,
        "start_at_login": supervisor.get("start_at_login") if supervisor_fresh else None,
        "backup": {
            **{key: backup.get(key)
            for key in ("created_at", "encrypted", "bytes", "reason", "verified", "files", "format", "scope")},
            "status": backup_status,
        },
        "services": rows,
        "note": "Runs on this laptop without Docker or Redis. Closing the browser leaves the assistant running in the tray.",
    }
