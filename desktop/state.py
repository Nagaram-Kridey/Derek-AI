"""Small atomic runtime records. No prompts, credentials or document contents."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".companion" / "runtime"
SERVICES = (
    "backend",
    "interactive",
    "research",
    "delivery",
    "scheduler",
    "companion",
    "ollama",
    "telegram",
    "backup",
)


def write_record(name, value):
    if name not in {*SERVICES, "supervisor"}:
        raise ValueError("Unknown local service")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    record = {**value, "updated_at": datetime.now(timezone.utc).isoformat()}
    descriptor, temporary = tempfile.mkstemp(prefix=name + "-", dir=RUNTIME)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream)
        os.replace(temporary, RUNTIME / (name + ".json"))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_record(name):
    if name not in {*SERVICES, "supervisor"}:
        return {}
    path = RUNTIME / (name + ".json")
    try:
        if path.stat().st_size > 16000:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def snapshot():
    now = datetime.now(timezone.utc)
    values = {}
    for name in (*SERVICES, "supervisor"):
        value = read_record(name)
        try:
            age = (now - datetime.fromisoformat(value["updated_at"])).total_seconds()
            fresh = 0 <= age < 30
        except (ValueError, KeyError, TypeError):
            fresh = False
        values[name] = {**value, "fresh": fresh}
    return values
