"""Consistent local SQLite snapshots. No account calls or private-chat history."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from .state import ROOT, write_record


def create_backup():
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings

    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.sqlite3":
        write_record(
            "backup",
            {
                "status": "not_applicable",
                "reason": "Use database-native backups for this installation.",
            },
        )
        return None
    folder = ROOT / ".companion" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    name = "derek-" + now.strftime("%Y%m%d-%H%M%S-") + os.urandom(3).hex()
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    descriptor, temporary = tempfile.mkstemp(
        prefix="snapshot-", suffix=".sqlite3", dir=folder
    )
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        source = sqlite3.connect(Path(database["NAME"]).resolve(), timeout=30)
        target = sqlite3.connect(temporary_path, timeout=30)
        try:
            source.backup(target, pages=128, sleep=0.02)
        finally:
            target.close()
            source.close()
        if key:
            from cryptography.fernet import Fernet

            body = Fernet(key.encode()).encrypt(temporary_path.read_bytes())
            path = folder / (name + ".sqlite3.fernet")
            with path.open("xb") as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
        else:
            path = folder / (name + ".sqlite3")
            os.replace(temporary_path, path)
        manifest = {
            "id": name,
            "created_at": now.isoformat(),
            "encrypted": bool(key),
            "file": path.name,
            "bytes": path.stat().st_size,
            "scope": "Normal assistant SQLite database only. Private companion chat and separate report files are not included.",
        }
        (folder / (name + ".json")).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        write_record(
            "backup",
            {
                "status": "ready",
                "created_at": manifest["created_at"],
                "encrypted": bool(key),
                "bytes": manifest["bytes"],
            },
        )
        return path
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    try:
        result = create_backup()
        print(
            "Local database snapshot saved."
            if result
            else "Use database-native backups for the configured database."
        )
    except Exception:
        write_record(
            "backup",
            {
                "status": "needs_attention",
                "reason": "The local snapshot could not be saved. Check available disk space and the configured encryption key.",
            },
        )
        raise SystemExit(
            "Local database backup needs attention; no credential values were logged."
        ) from None
