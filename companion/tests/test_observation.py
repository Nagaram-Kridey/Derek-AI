from unittest.mock import Mock, patch
import pytest
from desktop.observation import ObservationError, ObservationSession, WindowScope, validate_scope

SCOPE=WindowScope(123,456,100,'C:/fixture.exe')


def test_observation_is_off_until_consent_and_expires():
    session=ObservationSession()
    with pytest.raises(ObservationError): session.start()
    with patch('desktop.observation.validate_scope'),patch('desktop.observation.time.monotonic',return_value=100):
        session.approve(SCOPE)
    with patch('desktop.observation.time.monotonic',return_value=221):
        with pytest.raises(ObservationError): session.start()
    assert session.scope is None


def test_stale_process_instance_is_rejected():
    replacement=WindowScope(123,456,101,'C:/fixture.exe')
    with patch('desktop.observation.identity',return_value=replacement):
        with pytest.raises(ObservationError,match='changed'): validate_scope(SCOPE)


def test_revoke_terminates_reader_and_clears_consent():
    session=ObservationSession();session.scope=SCOPE
    process=Mock(is_alive=Mock(side_effect=[True,False]))
    pipe=Mock();session.process=process;session.pipe=pipe
    session.revoke()
    process.terminate.assert_called_once();pipe.close.assert_called_once()
    assert session.scope is None and session.process is None and session.pipe is None


def test_busy_reader_cannot_be_duplicated():
    session=ObservationSession();session.scope=SCOPE;session.expires=float('inf')
    session.process=Mock(is_alive=Mock(return_value=True))
    with patch('desktop.observation.validate_scope'):
        with pytest.raises(ObservationError,match='already running'): session.start()


def test_blocked_app_and_elevation_rules_are_explicit():
    from desktop.observation import BLOCKED
    assert {'chrome.exe','msedge.exe','cmd.exe','powershell.exe','bitwarden.exe','consent.exe'} <= BLOCKED


def test_unlocked_queries_desktop_through_win32_module():
    import sys
    from types import SimpleNamespace
    from desktop.observation import unlocked
    handle=Mock()
    api=SimpleNamespace(OpenInputDesktop=Mock(return_value=handle),GetUserObjectInformation=Mock(return_value='Default'))
    with patch.dict(sys.modules,{'win32service':api,'win32con':SimpleNamespace(DESKTOP_READOBJECTS=1,UOI_NAME=2)}):
        assert unlocked()
    api.GetUserObjectInformation.assert_called_once_with(handle,2)
    handle.CloseDesktop.assert_called_once()


def test_password_control_name_is_never_read():
    from desktop.observation import element_data
    class Password:
        CurrentIsPassword=True
        @property
        def CurrentName(self):
            pytest.fail('Protected names must not be read')
    assert element_data(Password(),1)['name']=='[protected control omitted]'


def test_plain_control_metadata_is_bounded_and_has_no_input_method():
    from types import SimpleNamespace
    from desktop.observation import element_data
    control=SimpleNamespace(CurrentIsPassword=False,CurrentName='a'*1000,CurrentLocalizedControlType='button',
        CurrentBoundingRectangle=SimpleNamespace(left=0,top=0,right=100,bottom=50),GetCurrentPropertyValue=lambda prop:prop==30031)
    item=element_data(control,1)
    assert len(item['name'])==250 and item['patterns']==['invoke']
    assert item['bounds']==[0,0,100,50]


def test_old_callback_cannot_consume_new_reader_after_reapproval():
    session=ObservationSession();old=session.generation
    session.revoke();session.scope=SCOPE;session.expires=float('inf')
    session.process=Mock();session.pipe=Mock()
    assert session.read_result(old) is None
    session.pipe.recv.assert_not_called()
    assert session.scope==SCOPE


def test_scope_rechecked_before_result_display():
    import queue
    session=ObservationSession();session.scope=SCOPE;session.expires=float('inf')
    session.process=Mock();session.pipe=Mock(poll=Mock(return_value=True))
    session.results=queue.Queue();session.results.put({'ok':True,'observation':{}})
    with patch('desktop.observation.validate_scope',side_effect=[None,ObservationError('locked')]):
        with pytest.raises(ObservationError,match='locked'): session.read_result(session.generation)


def test_unconsumed_result_blocks_another_read():
    session=ObservationSession();session.scope=SCOPE;session.expires=float('inf')
    session.process=Mock(is_alive=Mock(return_value=False));session.pipe=Mock(poll=Mock(return_value=True))
    with patch('desktop.observation.validate_scope'):
        with pytest.raises(ObservationError,match='already running'):session.start()


def test_spawn_failure_does_not_publish_unstarted_process():
    context=Mock();parent,child=Mock(),Mock()
    context.Pipe.return_value=(parent,child)
    process=Mock(pid=None,start=Mock(side_effect=OSError('sensitive details')))
    context.Process.return_value=process
    session=ObservationSession();session.scope=SCOPE;session.expires=float('inf')
    with patch('desktop.observation.validate_scope'),patch('desktop.observation.multiprocessing.get_context',return_value=context):
        with pytest.raises(ObservationError,match='could not start'):session.start()
    session.revoke()
    assert session.process is None and session.pipe is None
    process.join.assert_not_called();parent.close.assert_called_once();child.close.assert_called_once()


def test_waiting_for_ipc_never_blocks_result_poll():
    import queue
    session=ObservationSession();session.scope=SCOPE;session.expires=float('inf')
    session.process=Mock();session.pipe=Mock();session.results=queue.Queue()
    with patch('desktop.observation.validate_scope'):
        assert session.read_result(session.generation) is None
    session.pipe.recv.assert_not_called()


def test_permission_expiring_during_reader_cleanup_prevents_display():
    import queue
    session=ObservationSession();session.scope=SCOPE;session.expires=120
    session.process=Mock(is_alive=Mock(return_value=False));session.pipe=Mock()
    session.results=queue.Queue();session.results.put({'ok':True})
    with patch('desktop.observation.validate_scope'),patch('desktop.observation.time.monotonic',return_value=100) as clock:
        session.process.join.side_effect=lambda **_:setattr(clock,'return_value',121)
        with pytest.raises(ObservationError,match='expired'):session.read_result(session.generation)
    assert session.scope is None
