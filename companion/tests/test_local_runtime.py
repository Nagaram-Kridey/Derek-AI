import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import uuid

import pytest
from companion.client import ClientError, TurnInterrupted
from companion.private import PrivateClient
from companion.voice_state import VoiceState
from desktop.credentials import read_owner_token, remember_owner_token


def config(tmp_path):
    return SimpleNamespace(
        state_dir=tmp_path, api_url="http://127.0.0.1:18080", user_token="a" * 40
    )


def test_private_chat_keeps_history_separate_and_has_no_account_tools(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    client = PrivateClient(config(tmp_path))
    with patch.object(client, "generate", return_value="Local answer") as infer:
        assert client.turn("Discuss queues")["reply_text"] == "Local answer"
        blocked = client.turn("Remind me to drink water")
        assert "cannot schedule" in blocked["reply_text"]
        assert infer.call_count == 1
    assert len(client.messages()) == 4
    assert client.export().read_text(encoding="utf-8").startswith("# Derek")
    client.delete_current()
    assert client.history() == []
    assert not (tmp_path / "voice-state.json").exists()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com",
        "http://192.168.1.1:11434",
        "http://user:pass@localhost:11434",
        "http://127.0.0.1:11434/path",
    ],
)
def test_private_chat_refuses_remote_or_ambiguous_endpoint(
    tmp_path, monkeypatch, endpoint
):
    monkeypatch.setenv("OLLAMA_BASE_URL", endpoint)
    with pytest.raises(ClientError):
        PrivateClient(config(tmp_path))


def test_private_interruption_never_saves_a_completed_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    client = PrivateClient(config(tmp_path))
    with patch.object(client, "generate", side_effect=TurnInterrupted("Stopped")):
        with pytest.raises(TurnInterrupted):
            client.turn("A private prompt")
    assert client.pending_turn is None
    assert client.messages()[0][2] == "interrupted"
    assert len(client.messages()) == 1


def test_voice_state_retains_only_ids_and_is_token_bound(tmp_path):
    current = config(tmp_path)
    state = VoiceState(current)
    conversation, request = str(uuid.uuid4()), str(uuid.uuid4())
    state.save(conversation, request)
    saved = state.path.read_text(encoding="utf-8")
    assert current.user_token not in saved and "conversation_id" in saved
    assert state.load()["request_id"] == request
    current.user_token = "b" * 40
    assert VoiceState(current).load() == {}
    state.path.write_text('{"conversation_id":"not-a-uuid"}', encoding="utf-8")
    assert state.load() == {}


def test_windows_credential_blob_uses_unicode_and_reads_utf16(monkeypatch):
    token = "a" * 40
    native = SimpleNamespace(
        CRED_TYPE_GENERIC=1,
        CRED_PERSIST_LOCAL_MACHINE=2,
        CredRead=Mock(return_value={"CredentialBlob": token.encode("utf-16-le")}),
        CredWrite=Mock(),
    )
    monkeypatch.setitem(sys.modules, "win32cred", native)
    with patch.object(os, "name", "nt"):
        assert remember_owner_token("http://127.0.0.1:18080", token, "test-owner")
        assert read_owner_token("http://127.0.0.1:18080") == token
    assert native.CredWrite.call_args.args[0]["CredentialBlob"] == token


def test_runtime_records_are_atomic_bounded_and_stale_when_future(
    tmp_path, monkeypatch
):
    from desktop import state

    monkeypatch.setattr(state, "RUNTIME", tmp_path)
    state.write_record("backend", {"status": "ready"})
    assert state.snapshot()["backend"]["fresh"]
    path = tmp_path / "backend.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["updated_at"] = "2099-01-01T00:00:00+00:00"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert not state.snapshot()["backend"]["fresh"]
    path.write_text("x" * 16001, encoding="utf-8")
    assert state.read_record("backend") == {}
    assert state.read_record("../control") == {}


def test_process_group_attaches_existing_venv_children(monkeypatch):
    from desktop.process_group import ProcessGroup

    handle = Mock()
    native = SimpleNamespace(
        AssignProcessToJobObject=Mock(), IsProcessInJob=Mock(side_effect=[False, True])
    )
    windows = SimpleNamespace(OpenProcess=Mock(return_value=handle))
    monkeypatch.setitem(sys.modules, "win32job", native)
    monkeypatch.setitem(sys.modules, "win32api", windows)
    child = Mock(pid=123, is_running=Mock(return_value=True))
    parent = Mock(children=Mock(return_value=[child]))
    group = ProcessGroup.__new__(ProcessGroup)
    group.handle = Mock()
    process = Mock(pid=122, _handle=321, poll=Mock(return_value=None))
    with patch("psutil.Process", return_value=parent):
        group.add(process)
    assert native.AssignProcessToJobObject.call_count == 2
    assert handle.Close.call_count == 2
    group.close()
    assert group.handle is None


def test_service_log_rotates_without_a_child_holding_the_file(tmp_path):
    import io
    from desktop.logs import ServiceLog

    log = ServiceLog(tmp_path / "service.log")
    log.handler.maxBytes = 1000
    log.capture(io.BufferedReader(io.BytesIO(("Safe line\n" * 5000).encode())))
    log.close()
    assert (tmp_path / "service.log").exists()
    assert (tmp_path / "service.log.1").exists()
    assert len(list(tmp_path.glob("service.log*"))) == 2
    # Windows text streams expand LF to CRLF; one captured chunk is still bounded.
    assert 0 < (tmp_path / "service.log.1").stat().st_size <= 2 * 8193


def test_native_voice_does_not_open_before_startup_or_while_stopping():
    from desktop.supervisor import Supervisor

    owner = Supervisor.__new__(Supervisor)
    owner.stopping, owner.problem, owner.process_group = False, None, None
    with patch("desktop.supervisor.subprocess.Popen") as launch:
        assert not owner.voice_window()
        owner.stopping = True
        assert not owner.voice_window()
        launch.assert_not_called()
