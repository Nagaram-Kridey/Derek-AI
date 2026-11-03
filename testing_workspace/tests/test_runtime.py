import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from testing_workspace import __main__ as cli


def test_initialization_is_fresh_and_idempotent(tmp_path):
    with patch.object(cli, 'DATA', tmp_path), patch.object(cli, 'CONFIG', tmp_path / 'config.json'), patch('sys.argv', ['trial', 'init']):
        assert cli.main() == 0
        original = (tmp_path / 'config.json').read_text()
        config = json.loads(original)
        assert len(config['secret_key']) > 50
        assert config['invited_emails'] == []
        assert 'router_key' not in config
        assert cli.main() is None
        assert (tmp_path / 'config.json').read_text() == original


def test_backup_is_independent_sqlite_and_media(tmp_path):
    with sqlite3.connect(tmp_path / 'db.sqlite3') as db:
        db.execute('create table sample(value text)')
        db.execute("insert into sample values ('test only')")
    (tmp_path / 'media').mkdir()
    (tmp_path / 'media/a.txt').write_text('sample')
    with patch.object(cli, 'DATA', tmp_path):
        folder = cli.backup()
    with sqlite3.connect(folder / 'db.sqlite3') as db:
        assert db.execute('select value from sample').fetchone()[0] == 'test only'
    assert (folder / 'media/a.txt').read_text() == 'sample'


def test_restore_rejects_non_trial_snapshot(tmp_path):
    with patch.object(cli, 'DATA', tmp_path), patch.object(cli, 'owned_process', return_value=None), patch('sys.argv', ['trial', 'restore', str(tmp_path.parent)]):
        assert cli.main() == 1


def test_pid_record_never_matches_current_unrelated_process(tmp_path):
    import os
    import psutil
    proc = psutil.Process(os.getpid())
    (tmp_path / 'process.json').write_text(json.dumps({'pid': proc.pid, 'created': proc.create_time()}))
    with patch.object(cli, 'DATA', tmp_path):
        assert cli.owned_process() is None
