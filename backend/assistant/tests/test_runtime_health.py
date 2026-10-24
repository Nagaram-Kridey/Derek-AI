from datetime import datetime, timedelta, timezone
import json
from assistant.local_status import runtime_status


def test_stale_launcher_does_not_advertise_controls(settings, tmp_path):
    settings.LOCAL_EXECUTION = True
    settings.BASE_DIR = tmp_path / 'backend'
    folder = tmp_path / '.companion/runtime'; folder.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    record = {'status':'running','updated_at':(now-timedelta(minutes=2)).isoformat(),
              'stopping':True,'start_at_login':True,'voice_shortcut':'Ctrl+Alt+Space','issues':{'backup':'Failure'}}
    (folder/'supervisor.json').write_text(json.dumps(record))
    (folder/'backup.json').write_text(json.dumps({'status':'ready','updated_at':(now-timedelta(hours=5)).isoformat(),'verified':True,'format':1,'files':9}))
    status = runtime_status()
    assert status['supervisor_status'] == 'offline'
    assert status['start_at_login'] is None and status['voice_shortcut'] is None
    assert not status['stopping'] and status['issues'] == {}
    assert status['backup']['status'] == 'ready' and status['backup']['verified']


def test_old_backup_and_invalid_records_are_visible(settings,tmp_path):
    settings.LOCAL_EXECUTION = True
    settings.BASE_DIR = tmp_path/'backend'
    folder=tmp_path/'.companion/runtime'; folder.mkdir(parents=True)
    (folder/'supervisor.json').write_text('invalid')
    (folder/'backup.json').write_text(json.dumps({'status':'ready','updated_at':(datetime.now(timezone.utc)-timedelta(hours=27)).isoformat()}))
    status=runtime_status()
    assert status['backup']['status']=='overdue'
    assert all(row['status']=='offline' for row in status['services'])
