from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from assistant import commands, models as m


@pytest.mark.parametrize("lane", ["interactive", "delivery", "research", "scheduler"])
def test_local_lane_claims_saved_work_without_a_broker(
    user, settings, monkeypatch, tmp_path, lane
):
    from assistant import local_worker, tasks

    monkeypatch.setenv("DEREK_LOCAL_EXECUTION", "false")
    monkeypatch.setattr("desktop.state.RUNTIME", tmp_path)
    monkeypatch.setattr("sys.argv", ["local-worker", lane])
    settings.LOCAL_EXECUTION = True
    if lane == "interactive":
        command, _ = commands.submit(user, "hello")
    elif lane == "delivery":
        notification = m.Notification.objects.create(user=user, text="Saved update")
    elif lane == "research":
        m.AssistantState.objects.get_or_create(user=user)
        m.Report.objects.create(user=user, title="Saved request")
    research = SimpleNamespace(name="research", run=Mock())
    scheduler = SimpleNamespace(name="tick", run=Mock())
    with (
        patch("desktop.state.read_record", side_effect=[{}, {"stopping": True}]),
        patch("desktop.state.write_record"),
        patch("companion.journal.WorkerLock"),
        patch("django.db.close_old_connections"),
        patch("signal.signal"),
        patch.object(local_worker.threading, "Thread"),
        patch.object(tasks, "research_report", research),
        patch.object(tasks, "tick", scheduler),
    ):
        local_worker.main()
    if lane == "interactive":
        command.refresh_from_db()
        assert command.status == "completed"
    elif lane == "delivery":
        notification.refresh_from_db()
        assert notification.status == "in_app"
    elif lane == "research":
        research.run.assert_called_once()
    else:
        scheduler.run.assert_called_once()


def test_command_polling_does_not_consume_submit_budget(client):
    for _ in range(40):
        assert client.get("/v1/commands/").status_code == 200
    with patch("assistant.command_views.kick"):
        for index in range(30):
            response = client.post(
                "/v1/commands/",
                {"text": "hello", "request_id": str(index)},
                format="json",
            )
            assert response.status_code == 202
        assert (
            client.post(
                "/v1/commands/", {"text": "hello", "request_id": "extra"}, format="json"
            ).status_code
            == 429
        )
    assert client.get("/v1/commands/").status_code == 200


def test_cancellation_probe_keeps_callers_transaction_open(user):
    from django.db import connection

    command, _ = commands.submit(user, "hello")
    command.status = "running"
    command.save()
    with patch.object(connection, "close") as close:
        assert not commands.cancellation_probe(command.pk)()
        close.assert_not_called()
