"""Prepare only the configured database before starting the local runtime."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import sys

from .state import ROOT


def main():
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    database = settings.DATABASES["default"]
    if database["ENGINE"] == "django.db.backends.sqlite3":
        source = Path(database["NAME"]).resolve()
        if source.exists():
            # Keep one backup per day and an additional pre-migration snapshot.
            plan = MigrationExecutor(connection).migration_plan(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
            folder = ROOT / ".companion" / "backups"
            folder.mkdir(parents=True, exist_ok=True)
            name = (
                datetime.now(timezone.utc).strftime(
                    "local-%Y%m%d" + ("-migration-%H%M%S" if plan else "")
                )
                + ".sqlite3"
            )
            backup = folder / name
            if not backup.exists():
                with (
                    sqlite3.connect(source) as original,
                    sqlite3.connect(backup) as target,
                ):
                    original.backup(target)
            connection.close()
            with sqlite3.connect(source, timeout=30) as original:
                original.execute("PRAGMA journal_mode=WAL")
    call_command("migrate", interactive=False, verbosity=0)
    # Ensure a state row exists before lane queries use its paused flag.
    from django.contrib.auth import get_user_model
    from assistant.models import AssistantState

    for user in get_user_model().objects.filter(is_active=True):
        AssistantState.objects.get_or_create(user=user)
    from rest_framework.authtoken.models import Token
    from .credentials import read_owner_token, remember_owner_token, forget_owner_token

    api = "http://127.0.0.1:8000"
    saved = read_owner_token(api)
    if saved and not Token.objects.filter(key=saved, user__is_active=True).exists():
        forget_owner_token(api)
        saved = None
    legacy = os.getenv("LILYLEO_USER_TOKEN", "")
    if not saved and legacy:
        token = (
            Token.objects.select_related("user")
            .filter(key=legacy, user__is_active=True)
            .first()
        )
        if token:
            remember_owner_token(api, token.key, token.user.username)
    connection.close()


if __name__ == "__main__":
    main()
