from datetime import timedelta
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from freezegun import freeze_time
from assistant import models as m, services
from assistant.tasks import execute_run, execute_occurrence, tick
from assistant.scheduling import next_due, validate_schedule
from assistant.contracts import validate_workflow
from assistant.utils import reserve_usage

@pytest.fixture(autouse=True)
def no_broker():
    with patch("assistant.utils.kick"), patch("assistant.services.kick"), patch("assistant.views.kick"), patch("assistant.tasks.kick"):
        yield

def spec(tool="notify", args=None):
    return {"name": "Test routine", "steps": [{"tool": tool, "args": args or {"message": "Hello"}}], "allowed_tools": [tool], "allowed_domains": [], "allowed_paths": [], "trigger": {"kind": "manual"}}

def test_authentication_and_owner_isolation(user):
    api = APIClient()
    assert api.get("/v1/tasks/").status_code == 401
    assert api.post("/v1/auth/login", {"username": "owner", "password": "wrong"}).status_code == 401
    response = api.post("/v1/auth/login", {"username": "owner", "password": "testing-a-long-password"})
    assert response.status_code == 200
    api.credentials(HTTP_AUTHORIZATION="Token " + response.data["token"])
    assert api.get("/v1/status/").status_code == 200
    other = get_user_model().objects.create_user(username="other", is_active=False)
    foreign = m.Conversation.objects.create(user=other, title="Private")
    assert api.get(f"/v1/conversations/{foreign.id}/").status_code == 404
    assert api.post("/v1/auth/logout").status_code == 200
    assert api.get("/v1/status/").status_code == 401

def test_workflow_review_and_version_change(client, user):
    response = client.post("/v1/workflows/", spec(), format="json")
    assert response.status_code == 201
    identifier = response.data["id"]
    assert client.post(f"/v1/workflows/{identifier}/run/").status_code == 400
    assert client.post(f"/v1/workflows/{identifier}/enable/").status_code == 200
    run = client.post(f"/v1/workflows/{identifier}/run/").data
    assert run["status"] == "queued"
    client.patch(f"/v1/workflows/{identifier}/", {"name": "Edited"}, format="json")
    workflow = m.Workflow.objects.get(pk=identifier)
    assert workflow.version == 2 and not workflow.enabled
    assert m.WorkflowRun.objects.get(pk=run["id"]).status == "cancelled"

@pytest.mark.parametrize("changes", [{"allowed_tools": ["shell.run"]}, {"steps": [{"tool": "notify", "args": {"message": "x", "confirm": True}}]}, {"allowed_domains": ["*.example.com"]}, {"allowed_paths": ["C:\\"]}])
def test_rejects_unregistered_or_unsafe_permissions(changes):
    with pytest.raises(ValueError):
        validate_workflow({**spec(), **changes})

def test_browser_scope_and_expected_page():
    draft = spec("browser.run", {"actions": [{"type": "navigate", "url": "https://example.com"}, {"type": "click", "selector": "#submit", "expected_url": "https://example.com", "expected_text": "Ready"}]})
    draft["allowed_domains"] = ["example.com"]
    assert validate_workflow(draft)
    draft["steps"][0]["args"]["actions"][0]["url"] = "https://other.com"
    with pytest.raises(ValueError):
        validate_workflow(draft)

@freeze_time("2026-10-10 03:00:00+00:00")
def test_timezone_and_daily_weekly_recurrence():
    assert next_due(validate_schedule({"kind": "daily", "time": "09:00"})).isoformat() == "2026-10-10T09:00:00+05:30"
    assert next_due(validate_schedule({"kind": "weekly", "time": "09:00", "weekdays": [0]})).weekday() == 0
    with pytest.raises(ValueError):
        validate_schedule({"kind": "weekly", "time": "09:00", "weekdays": [7]})

def test_due_reminder_dispatches_once(client, user):
    task = services.create_task(user, {"name": "Water", "payload": {"message": "Drink water"}, "schedule": {"kind": "once", "at": (timezone.now()+timedelta(minutes=1)).isoformat()}})
    with freeze_time(timezone.now()+timedelta(minutes=2)):
        tick()
        tick()
    assert m.ScheduledOccurrence.objects.filter(task=task).count() == 1
    row = m.ScheduledOccurrence.objects.get(task=task)
    execute_occurrence(str(row.id))
    execute_occurrence(str(row.id))
    assert m.Notification.objects.filter(user=user).count() == 1
    assert not m.ScheduledTask.objects.get(pk=task.id).enabled

def test_desktop_approval_lease_and_checkpoint(client, user):
    draft = spec("file.delete", {"path": "C:\\Users\\Owner\\Documents\\note.txt"})
    draft["allowed_paths"] = ["C:\\Users\\Owner\\Documents"]
    workflow = services.enable_workflow(services.create_workflow(user, draft))
    run = services.start_run(workflow)
    execute_run(str(run.id))
    token = client.post("/v1/devices/", {"name": "PC"}).data["credential"]
    device_api = APIClient()
    device_api.credentials(HTTP_AUTHORIZATION="Device " + token)
    job = device_api.post("/v1/desktop/jobs/claim/", {}).data["job"]
    assert job["approved_risk"] is None
    assert device_api.get("/v1/status/").status_code == 401
    assert device_api.post(f"/v1/desktop/jobs/{job['id']}/complete/", {"lease_token": "wrong", "status": "completed"}, format="json").status_code == 401
    response = device_api.post(f"/v1/desktop/jobs/{job['id']}/complete/", {"lease_token": job["lease_token"], "status": "needs_approval", "risk": "permanent_delete", "result": {"next_action": 0}}, format="json")
    assert response.status_code == 200
    approval = m.Approval.objects.get(run=run)
    assert client.post(f"/v1/approvals/{approval.id}/approve/").status_code == 200
    resumed = device_api.post("/v1/desktop/jobs/claim/", {}).data["job"]
    assert resumed["id"] == job["id"] and resumed["approved_risk"] == "permanent_delete"
    body = {"lease_token": resumed["lease_token"], "status": "completed", "result": {"deleted": "note.txt", "next_action": 1}}
    assert device_api.post(f"/v1/desktop/jobs/{job['id']}/complete/", body, format="json").status_code == 200
    assert device_api.post(f"/v1/desktop/jobs/{job['id']}/complete/", body, format="json").status_code == 200
    run.refresh_from_db()
    assert run.status == "completed" and len(run.results) == 1

def test_pause_and_expired_lease_no_replay(client, user):
    draft = spec("file.read", {"path": "C:\\Users\\Owner\\Documents\\note.txt"})
    draft["allowed_paths"] = ["C:\\Users\\Owner\\Documents"]
    run = services.start_run(services.enable_workflow(services.create_workflow(user, draft)))
    execute_run(str(run.id))
    token = client.post("/v1/devices/", {}).data["credential"]
    device_api = APIClient(); device_api.credentials(HTTP_AUTHORIZATION="Device "+token)
    client.post("/v1/control/pause/", {"paused": True}, format="json")
    assert device_api.post("/v1/desktop/jobs/claim/").data["job"] is None
    client.post("/v1/control/pause/", {"paused": False}, format="json")
    job = device_api.post("/v1/desktop/jobs/claim/").data["job"]
    m.DesktopJob.objects.filter(pk=job["id"]).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
    tick()
    assert device_api.post("/v1/desktop/jobs/claim/").data["job"] is None
    run.refresh_from_db(); assert run.status == "needs_attention"

def test_usage_budget_and_secret_export(client, user, settings):
    settings.DAILY_MODEL_CALL_LIMIT = 1
    reserve_usage(user, 100)
    with pytest.raises(RuntimeError):
        reserve_usage(user, 1)
    m.ProviderCredential.objects.create(user=user, provider="google", ciphertext="do-not-export")
    response = client.get("/v1/export/")
    assert "do-not-export" not in str(response.data)

def test_missing_provider_returns_clear_status(client, settings):
    settings.GEMINI_API_KEY = ""
    response = client.post("/v1/turn", {"text": "Hello"}, format="json")
    assert response.status_code == 503 and "GEMINI_API_KEY" in response.data["detail"]

def test_mocked_turn_dispatches_real_reminder(client, user):
    with patch("assistant.services.BudgetGateway") as Mock:
        Mock.return_value.chat.side_effect = [{"text": "", "tool_calls": [{"name": "schedule_task", "args": {"name": "Water", "kind": "reminder", "payload": {"message": "Water"}, "schedule": {"kind": "once", "at": (timezone.now()+timedelta(minutes=10)).isoformat()}}}]}, {"text": "Reminder scheduled", "tool_calls": []}]
        response = client.post("/v1/turn", {"text": "Remind me in 10 minutes"}, format="json")
    assert response.status_code == 200 and response.data["reply_text"] == "Reminder scheduled"
    assert m.ScheduledTask.objects.filter(user=user).count() == 1
    assert m.Message.objects.filter(conversation_id=response.data["conversation_id"]).count() == 3

def test_telegram_allowlist_and_update_dedup(client, settings, user):
    settings.TELEGRAM_WEBHOOK_SECRET = "a-secret"
    settings.TELEGRAM_CHAT_ID = "123"
    api = APIClient()
    payload = {"update_id": 10, "message": {"chat": {"id": 123}, "text": "Hello"}}
    assert api.post("/v1/telegram/webhook/", payload, format="json").status_code == 403
    api.credentials(HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="a-secret")
    assert api.post("/v1/telegram/webhook/", payload, format="json").status_code == 200
    api.post("/v1/telegram/webhook/", payload, format="json")
    assert m.TelegramUpdate.objects.count() == 1
    payload["update_id"] = 11; payload["message"]["chat"]["id"] = 999
    api.post("/v1/telegram/webhook/", payload, format="json")
    assert m.TelegramUpdate.objects.count() == 1
