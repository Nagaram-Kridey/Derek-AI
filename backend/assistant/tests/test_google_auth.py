"""Identity replay, role and cross-user boundaries; no real Google calls."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient

from assistant import auth_views
from assistant import models as m
from assistant.commands import execute_tool, submit
from assistant.permissions import is_admin

pytestmark = pytest.mark.django_db


@pytest.fixture
def google(settings, monkeypatch):
    settings.GOOGLE_SIGN_IN_CLIENT_ID = "test.apps.googleusercontent.com"
    claims = {"iss": "https://accounts.google.com", "aud": settings.GOOGLE_SIGN_IN_CLIENT_ID,
              "sub": "stable-google-subject", "email": "tester@gmail.com", "email_verified": True,
              "given_name": "Tester"}
    monkeypatch.setattr(auth_views, "verify_google_credential", lambda credential: dict(claims))
    return claims


def begin(client, claims):
    response = client.post("/v1/auth/google/challenge/", {}, format="json")
    assert response.status_code == 200
    claims["nonce"] = response.data["nonce"]
    return {"credential": "signed-by-google-test-fixture", "challenge_id": response.data["challenge_id"]}


def test_google_signup_and_repeat_identity(google, user):
    client = APIClient()
    payload = begin(client, google)
    response = client.post("/v1/auth/google/", payload, format="json")
    assert response.status_code == 200
    assert response.data["is_admin"] is False
    assert response.data["auth_provider"] == "google"
    tester = m.GoogleIdentity.objects.get().user
    assert not tester.has_usable_password()
    assert not is_admin(tester)
    assert m.AssistantPreferences.objects.get(user=tester).interactive_profile == "configured"
    assert is_admin(user)
    client.credentials(HTTP_AUTHORIZATION="Token " + response.data["token"])
    assert client.get("/v1/auth/me/").data["email"] == "tester@gmail.com"
    client.credentials()
    payload = begin(client, google)
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 200
    assert m.GoogleIdentity.objects.count() == 1


def test_google_replay_browser_and_expiry(google):
    client = APIClient()
    payload = begin(client, google)
    stranger = APIClient()
    assert stranger.post("/v1/auth/google/", payload, format="json").status_code == 401
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 200
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 401
    payload = begin(client, google)
    m.GoogleLoginChallenge.objects.update(expires_at=timezone.now())
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 401


@pytest.mark.parametrize("key,value", [("email_verified", False), ("aud", "wrong"), ("iss", "attacker"), ("nonce", "wrong")])
def test_google_rejects_invalid_claims(google, key, value):
    client = APIClient()
    payload = begin(client, google)
    google[key] = value
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 401
    assert not m.GoogleIdentity.objects.exists()


def test_no_email_owner_link(google, user):
    user.email = google["email"]
    user.save()
    client = APIClient()
    payload = begin(client, google)
    assert client.post("/v1/auth/google/", payload, format="json").status_code == 200
    assert m.GoogleIdentity.objects.get().user_id != user.pk
    assert not m.GoogleIdentity.objects.get().user.is_staff


def test_disabled_google_fails_closed(settings):
    settings.GOOGLE_SIGN_IN_CLIENT_ID = ""
    client = APIClient()
    assert client.get("/v1/auth/config/").data["google_enabled"] is False
    assert client.post("/v1/auth/google/challenge/", {}, format="json").status_code == 503
    assert client.post("/v1/auth/google/", {}, format="json").status_code == 503


def test_owner_password_survives_multiple_users(user):
    get_user_model().objects.create_user(username="tester", password=None)
    client = APIClient()
    response = client.post("/v1/auth/login", {"username": "owner", "password": "testing-a-long-password"}, format="json")
    assert response.status_code == 200
    assert response.data["is_admin"] is True


def test_nonadmin_cannot_use_password_or_owner_controls(user):
    tester = get_user_model().objects.create_user(username="tester", password="long-test-password")
    client = APIClient()
    assert client.post("/v1/auth/login", {"username": "tester", "password": "long-test-password"}, format="json").status_code == 403
    client.force_authenticate(tester)
    for endpoint in ("/v1/devices/", "/v1/local/voice/", "/v1/local/startup/", "/v1/control/pause/", "/v1/tasks/", "/v1/workflows/", "/v1/calendar/connect/"):
        assert client.post(endpoint, {}, format="json").status_code == 403, endpoint
    conversation = m.Conversation.objects.create(user=user, title="Owner private")
    assert client.get(f"/v1/conversations/{conversation.pk}/").status_code == 404
    assert client.get("/v1/conversations/").data == []
    with pytest.raises(ValueError, match="Unknown conversation"):
        submit(tester, "hello", conversation_id=str(conversation.pk))
    command, _ = submit(tester, "hello")
    with pytest.raises(ValueError, match="unavailable"):
        execute_tool(command, 0, "send_whatsapp_message", {}, None, {})


def test_tester_context_excludes_host_capabilities_and_runtime(settings):
    settings.LOCAL_EXECUTION = True
    settings.TELEGRAM_BOT_TOKEN = "configured-test-only"
    tester = get_user_model().objects.create_user(username="tester", password=None)
    client = APIClient()
    client.force_authenticate(tester)
    with patch("assistant.local_status.runtime_status", side_effect=AssertionError("Host status must not be read")):
        status = client.get("/v1/status/")
        catalog = client.get("/v1/capabilities/")
    assert status.status_code == catalog.status_code == 200
    assert status.data["runtime"] == {"managed": False}
    assert status.data["integrations"] == {}
    assert "language_model" not in status.data
    assert {row["id"] for row in catalog.data["capabilities"]} == {"private_chat", "personal_memory"}
    audio = SimpleUploadedFile("note.wav", b"not-real-audio", content_type="audio/wav")
    with patch("assistant.integrations.voice.transcribe_audio", side_effect=AssertionError("Tester cannot transcribe")):
        assert client.post("/v1/turn", {"audio": audio}, format="multipart").status_code == 403


def test_tester_cannot_read_other_account_records(user):
    tester = get_user_model().objects.create_user(username="tester", password=None)
    client = APIClient()
    client.force_authenticate(tester)
    command, _ = submit(user, "Owner's private text")
    assert client.get(f"/v1/commands/{command.pk}/").status_code == 404
    assert client.get(f"/v1/commands/{command.pk}/events/").status_code == 404
    report = m.Report.objects.create(user=user, title="Private owner report")
    assert client.get(f"/v1/reports/{report.pk}/detail/").status_code == 404
    assert client.get("/v1/reports/").data == []
    assert client.get("/v1/commands/").data == []
    memory = m.PersonalMemory.objects.create(user=user, title="Private", content="Owner detail", key="private", fingerprint="private")
    assert client.get("/v1/memories/").data["memories"] == []
    assert client.patch(f"/v1/memories/{memory.pk}/", {"version": memory.version, "content": "intrusion"}, format="json").status_code in (400, 404)
    memory.refresh_from_db()
    assert memory.content == "Owner detail"


def test_create_owner_with_existing_tester_does_not_promote_tester():
    tester = get_user_model().objects.create_user(username="tester", password=None)
    with patch("assistant.management.commands.create_owner.getpass", return_value="new-long-owner-password"):
        call_command("create_owner", "new-owner", verbosity=0)
    owner = get_user_model().objects.get(username="new-owner")
    assert is_admin(owner) and owner.has_usable_password()
    tester.refresh_from_db()
    assert not is_admin(tester) and not tester.has_usable_password()
    with pytest.raises(CommandError, match="already exists"):
        call_command("create_owner", "another-owner", verbosity=0)


def test_document_gis_referrer_and_api_privacy(settings):
    from django.http import HttpResponse
    from django.test import RequestFactory

    from assistant.middleware import WorkspaceHeaders
    middleware = WorkspaceHeaders(lambda request: HttpResponse(""))
    settings.DEBUG = True
    assert middleware(RequestFactory().get("/"))["Referrer-Policy"] == "no-referrer-when-downgrade"
    assert middleware(RequestFactory().get("/v1/auth/config/"))["Referrer-Policy"] == "no-referrer"
    settings.DEBUG = False
    assert middleware(RequestFactory().get("/"))["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_demoted_owner_cannot_dispatch_saved_work(user):
    from assistant import services, tasks
    workflow = m.Workflow.objects.create(user=user, name="Approved", enabled=True, reviewed_at=timezone.now(), steps=[], trigger={})
    run = m.WorkflowRun.objects.create(user=user, workflow=workflow, snapshot={"version": workflow.version, "steps": []})
    task = m.ScheduledTask.objects.create(user=user, name="Reminder", kind="reminder", payload={"message": "private"}, schedule={})
    occurrence = m.ScheduledOccurrence.objects.create(task=task, scheduled_for=timezone.now())
    report = m.Report.objects.create(user=user, title="Research")
    user.is_staff = False
    user.save(update_fields=["is_staff"])
    assert not services.run_allowed(run)
    with pytest.raises(ValueError, match="administrator"):
        services.start_run(workflow)
    with patch("assistant.tasks.build_report", side_effect=AssertionError("Demoted owner cannot research")):
        tasks.research_report(str(report.pk))
        tasks.execute_occurrence(str(occurrence.pk))
        tasks.execute_run(str(run.pk))
    assert not m.Notification.objects.exists()
    report.refresh_from_db()
    occurrence.refresh_from_db()
    assert report.status == "cancelled" and occurrence.status == "cancelled"


def test_nonadmin_report_delivery_is_terminal_without_sending():
    from assistant import tasks
    tester = get_user_model().objects.create_user(username="tester", password=None)
    report = m.Report.objects.create(user=tester, title="Saved", status="completed", progress={"telegram_delivery": {"status": "pending"}})
    with patch("assistant.integrations.telegram.send_document", side_effect=AssertionError("Cannot send tester report")):
        tasks.send_report_file(str(report.pk))
    report.refresh_from_db()
    assert report.progress["telegram_delivery"]["status"] == "cancelled"
