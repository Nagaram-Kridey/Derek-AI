"""Prepare only the configured database before starting the local runtime."""

import os
from pathlib import Path
import sqlite3
import sys

from .state import ROOT


def prepare_sqlite(connection, settings, backup_folder):
    """Finish recovery preparation before the caller applies any migrations."""
    from django.db.migrations.executor import MigrationExecutor
    database = settings.DATABASES['default']
    if database['ENGINE'] != 'django.db.backends.sqlite3' or str(database['NAME']) == ':memory:':
        return
    source = Path(database['NAME']).resolve()
    if not source.exists():
        return
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan and 'assistant_report' in connection.introspection.table_names():
        from .recovery import create_archive, verify_archive
        archive, _ = create_archive(source, settings.MEDIA_ROOT, backup_folder, settings.CREDENTIAL_ENCRYPTION_KEY)
        verify_archive(archive, settings.CREDENTIAL_ENCRYPTION_KEY)
    connection.close()
    with sqlite3.connect(source, timeout=30) as original:
        original.execute('PRAGMA journal_mode=WAL')


def main():
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection
    prepare_sqlite(connection, settings, ROOT / '.companion/backups')
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
