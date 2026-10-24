from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import json
import pytest
from desktop import supervisor as s, state


@pytest.fixture
def owner():
    with patch.object(s, 'child_environment', return_value={}):
        return s.Supervisor(open_page=False)


def test_optional_failure_does_not_prevent_service_monitoring(owner):
    owner.backend_ready = Mock(return_value=True)
    with patch.object(s, 'write_record') as record:
        assert not owner.optional('tray', Mock(side_effect=OSError('secret exception body')))
        process = Mock(pid=42, poll=Mock(return_value=None))
        owner.monitor_service('backend', process)
        assert record.call_args.args[1]['status'] == 'ready'
        assert owner.issues == {'tray': 'OSError'}
        assert owner.optional('tray', Mock())
        assert owner.issues == {}


def test_status_io_failure_is_nonfatal(caplog):
    with patch.object(s,'atomic_record',side_effect=PermissionError('SECRET')), patch.object(s,'_record_warning_at',0):
        assert not s.write_record('backend',{'status':'ready'})
    assert 'SECRET' not in caplog.text


def test_owned_child_restarts_only_after_backoff(owner):
    owner.logs['research'] = Mock()
    process = Mock(poll=Mock(return_value=1))
    with patch.object(s,'write_record'), patch.object(s.time,'monotonic',return_value=100), patch.object(owner,'launch') as launch:
        owner.monitor_service('research', process)
        assert owner.retry_at['research'] == 102
        assert owner.issues['service_research'] == 'ServiceExited'
        launch.assert_not_called()
    with patch.object(s.time,'monotonic',return_value=103), patch.object(owner,'launch') as launch:
        owner.monitor_service('research',process)
        launch.assert_called_once_with('research')
        assert 'research' not in owner.retry_at


def test_failed_backup_retries_without_stopping_workers(owner):
    owner.backup_process = Mock(poll=Mock(return_value=1))
    with patch.object(s.time,'monotonic',return_value=100): owner.maintain_backup()
    assert owner.next_backup_at == 1000
    assert owner.issues['backup'] == 'BackupFailed'
    assert not owner.stopping


def test_idle_voice_cannot_hold_drain_forever(owner):
    owner.voice_process = Mock(poll=Mock(return_value=None))
    owner.drain_started = 100
    with patch.object(s.time,'monotonic',return_value=200): assert not owner.drain_complete()
    with patch.object(s.time,'monotonic',return_value=281): assert owner.drain_complete()


def test_daily_backup_has_daily_freshness(tmp_path, monkeypatch):
    monkeypatch.setattr(state,'RUNTIME',tmp_path)
    value={'status':'ready','updated_at':(datetime.now(timezone.utc)-timedelta(hours=5)).isoformat()}
    for name in ['backup','backend']:
        (tmp_path / (name+'.json')).write_text(json.dumps(value))
    assert state.snapshot()['backup']['fresh']
    assert not state.snapshot()['backend']['fresh']


def test_record_retries_transient_windows_sharing_error(tmp_path, monkeypatch):
    monkeypatch.setattr(state,'RUNTIME',tmp_path)
    original = state.os.replace
    attempts=[]
    def replace(src,dst):
        attempts.append(dst)
        if len(attempts)==1: raise PermissionError('sharing violation')
        original(src,dst)
    with patch.object(state.os,'replace',side_effect=replace), patch.object(state.time,'sleep'):
        state.write_record('backend',{'status':'ready'})
    assert len(attempts)==2 and state.read_record('backend')['status']=='ready'


def test_failed_attachment_rolls_back_service(owner):
    process = Mock()
    owner.process_group = Mock(add=Mock(side_effect=RuntimeError('attachment failed')))
    with patch.object(s.subprocess,'Popen',return_value=process), patch('desktop.logs.ServiceLog'), patch('desktop.process_group.stop_spawned_process') as stop:
        with pytest.raises(RuntimeError): owner.launch('backend')
        stop.assert_called_once_with(process)
    assert 'backend' not in owner.processes


def test_backup_attachment_failure_keeps_retry_issue(owner):
    owner.next_backup_at = 0
    process = Mock()
    owner.process_group = Mock(add=Mock(side_effect=RuntimeError('attachment failed')))
    with patch.object(s.time,'monotonic',return_value=100), patch.object(s.subprocess,'Popen',return_value=process), patch('desktop.process_group.stop_spawned_process') as stop:
        assert not owner.optional('backup_launcher', owner.maintain_backup, clear=False)
        stop.assert_called_once_with(process)
        assert owner.backup_process is None
        assert owner.optional('backup_launcher', owner.maintain_backup, clear=False)
        assert owner.issues['backup_launcher'] == 'RuntimeError'


def test_initial_spawn_failure_can_recover(owner):
    with patch.object(s,'write_record'), patch.object(s.time,'monotonic',return_value=100):
        owner.monitor_service('backend',None)
    with patch.object(s.time,'monotonic',return_value=103), patch.object(owner,'launch') as launch:
        owner.monitor_service('backend',None)
        launch.assert_called_once_with('backend')


def test_failed_attachment_cleanup_escalates_only_owned_process():
    import subprocess
    from desktop.process_group import stop_spawned_process
    process = Mock(pid=42, poll=Mock(return_value=None))
    process.wait.side_effect = [subprocess.TimeoutExpired('owned',5), 0]
    child = Mock()
    with patch('psutil.Process', return_value=Mock(children=Mock(return_value=[child]))):
        stop_spawned_process(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    child.terminate.assert_called_once()
