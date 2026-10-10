from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from companion.policy import PathPolicy, PolicyError, DomainPolicy, ApprovalRequired, detect_risk
from companion.files import execute_file
from companion.journal import Journal
from companion.runner import Worker

def test_folder_scope_and_protected_state(tmp_path):
    approved = tmp_path / "approved"; approved.mkdir()
    state = approved / "private"; state.mkdir()
    policy = PathPolicy([str(approved)], [state])
    for value in [str(tmp_path / "outside"), str(approved / ".." / "outside"), str(state / "cookies")]:
        with pytest.raises(PolicyError): policy.check(value)
    assert policy.check(str(approved / "note.txt")) == approved / "note.txt"

def test_files_no_overwrite_or_unapproved_delete(tmp_path):
    policy = PathPolicy([str(tmp_path)])
    path = tmp_path / "note.txt"
    execute_file("file.write", {"path": str(path), "content": "hello"}, policy)
    with pytest.raises(PolicyError): execute_file("file.write", {"path": str(path), "content": "replacement"}, policy)
    with pytest.raises(ApprovalRequired): execute_file("file.delete", {"path": str(path)}, policy)
    assert path.read_text() == "hello"
    execute_file("file.delete", {"path": str(path)}, policy, "permanent_delete")
    assert not path.exists()

def test_symlink_escape_is_rejected(tmp_path):
    folder = tmp_path / "safe"; folder.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    link = folder / "link"
    try: link.symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip("Host does not permit symlink creation")
    with pytest.raises(PolicyError): PathPolicy([str(folder)]).check(str(link / "secret"))

def test_browser_domain_and_private_network_rejected():
    public = lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))]
    policy = DomainPolicy(["example.com"], public)
    assert policy.check("https://example.com/path")
    for url in ["https://evil.com", "http://example.com", "https://example.com:8080", "https://a.example.com"]:
        with pytest.raises(PolicyError): policy.check(url)
    policy.resolver = lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))]
    with pytest.raises(PolicyError): policy.check("https://example.com")

@pytest.mark.parametrize("text,risk", [("Pay now", "payment"), ("Checkout", "purchase"), ("Change password", "account_security"), ("Delete permanently", "permanent_delete")])
def test_sensitive_action_detection(text,risk): assert detect_risk(text) == risk

def test_worker_completed_file_is_not_replayed(tmp_path):
    folder = tmp_path / "safe"; folder.mkdir()
    config = SimpleNamespace(state_dir=tmp_path / "state", browser_profile=tmp_path / "profile")
    client = Mock(); client.heartbeat.return_value = {}
    worker = Worker(config, client)
    job = {"id": "job1", "tool": "file.write", "args": {"path": str(folder / "note.txt"), "content": "hello"}, "policy": {"allowed_paths": [str(folder)]}, "approved_risk": None}
    assert worker.execute(job)["status"] == "completed"
    assert worker.execute(job)["status"] == "completed"
    assert (folder / "note.txt").read_text() == "hello"
    worker.journal.close()

def test_journal_uncertain_mutation_stops_retry(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite3")
    job = {"id": "1", "tool": "browser.run", "args": {"actions": []}, "policy": {}}
    journal.prepare(job); journal.pending("1", 0)
    from companion.policy import AttentionRequired
    with pytest.raises(AttentionRequired): journal.prepare(job)
    journal.resolve("1", 1)
    assert journal.prepare(job)[0] == 1
    journal.close()
