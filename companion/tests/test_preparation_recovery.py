import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet
import pytest
from desktop.prepare import prepare_sqlite
from desktop.recovery import RecoveryError, verify_archive


def installation(tmp_path):
    source = tmp_path / 'source.sqlite3'
    with sqlite3.connect(source) as db:
        db.executescript('CREATE TABLE django_migrations (id INTEGER); CREATE TABLE assistant_report (docx TEXT, pdf TEXT);')
    settings = SimpleNamespace(DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':source}},
        MEDIA_ROOT=tmp_path / 'media', CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode())
    connection = Mock()
    connection.introspection.table_names.return_value = ['assistant_report']
    return source, settings, connection


def test_pending_migration_requires_encrypted_verified_backup(tmp_path):
    source, settings, connection = installation(tmp_path)
    executor = Mock(migration_plan=Mock(return_value=['pending']))
    with patch('django.db.migrations.executor.MigrationExecutor',return_value=executor):
        prepare_sqlite(connection, settings, tmp_path / 'backups')
    archives = list((tmp_path / 'backups').glob('*.derekbackup'))
    assert len(archives) == 1
    assert verify_archive(archives[0],settings.CREDENTIAL_ENCRYPTION_KEY)['verified']
    assert not list((tmp_path / 'backups').glob('*.sqlite3'))
    with sqlite3.connect(source) as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'


def test_invalid_key_stops_preparation_before_database_mode_change(tmp_path):
    source, settings, connection = installation(tmp_path)
    settings.CREDENTIAL_ENCRYPTION_KEY = ''
    with patch('django.db.migrations.executor.MigrationExecutor',return_value=Mock(migration_plan=Mock(return_value=['pending']))):
        with pytest.raises(RecoveryError):
            prepare_sqlite(connection,settings,tmp_path/'backups')
    connection.close.assert_not_called()
    with sqlite3.connect(source) as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'


def test_no_schema_change_does_not_create_startup_backup(tmp_path):
    _, settings, connection = installation(tmp_path)
    with patch('django.db.migrations.executor.MigrationExecutor',return_value=Mock(migration_plan=Mock(return_value=[]))), patch('desktop.recovery.create_archive') as archive:
        prepare_sqlite(connection,settings,tmp_path/'backups')
    archive.assert_not_called()
