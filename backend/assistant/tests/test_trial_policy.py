"""Untrusted invited testers cannot exercise the separate admin's host powers."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from assistant.commands import submit
from assistant.integrations.errors import ConfigError
from assistant.models import GoogleIdentity, UsageDay
from assistant.permissions import can_use_tools
from assistant.utils import reserve_usage

pytestmark = pytest.mark.django_db

@pytest.fixture
def trial(settings):
    settings.TEST_WORKSPACE = True
    settings.TEST_INVITED_EMAILS = {"invited@gmail.com"}
    settings.TEST_DAILY_CALL_LIMIT = 20
    settings.TEST_SHARED_DAILY_CALL_LIMIT = 200
    return settings

def test_admin_is_analytics_only_not_host(client, user, trial):
    assert not can_use_tools(user)
    assert client.get("/v1/admin/analytics/").status_code == 200
    for path in ["/v1/local/voice/", "/v1/devices/", "/v1/workflows/", "/v1/calendar/events/"]:
        assert client.get(path).status_code == 403
    assert client.get("/v1/tasks/").status_code == 200
    assert client.post("/v1/turn", {"text":"hi", "input_mode":"voice"}, format="json").status_code == 200

def test_invitation_revocation_on_explicit_analytics_permission(user, trial):
    from rest_framework.authtoken.models import Token
    user.is_staff = True
    user.save()
    GoogleIdentity.objects.create(user=user,subject="sub",email="invited@gmail.com")
    token = Token.objects.create(user=user)
    client=APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
    assert client.get("/v1/admin/analytics/").status_code == 200
    trial.TEST_INVITED_EMAILS = set()
    assert client.get("/v1/admin/analytics/").status_code == 401
    assert client.get("/v1/conversations/").status_code == 401

def test_single_request_and_replay(user, trial):
    first, created = submit(user,"hello",request_id="one")
    repeated, created = submit(user,"hello",request_id="one")
    assert repeated.pk == first.pk and not created
    with pytest.raises(ValueError,match="unfinished"):
        submit(user,"second",request_id="two")
    assert first.model_profile == "configured"
    with pytest.raises(ValueError,match="configured"):
        submit(user,"other",request_id="three",profile="gemini")

def test_shared_and_individual_reservation(user, trial):
    other=get_user_model().objects.create_user("other",is_staff=True)
    reserve_usage(user,1)
    row=UsageDay.objects.get(user=user)
    row.model_calls=20;row.save()
    with pytest.raises(ConfigError):reserve_usage(user,1)
    row.model_calls=200;row.save()
    with pytest.raises(ConfigError,match="shared"):reserve_usage(other,1)
    assert not UsageDay.objects.filter(user=other).exists()


def test_uninvited_verified_google_denied_before_creation(trial, monkeypatch):
    from assistant import auth_views
    trial.GOOGLE_SIGN_IN_CLIENT_ID="trial.apps.googleusercontent.com"
    client=APIClient()
    challenge=client.post("/v1/auth/google/challenge/",{},format="json").data
    claims={"iss":"https://accounts.google.com","aud":trial.GOOGLE_SIGN_IN_CLIENT_ID,
            "sub":"not-invited", "email":"stranger@gmail.com", "email_verified":True,
            "nonce":challenge["nonce"]}
    monkeypatch.setattr(auth_views,"verify_google_credential",lambda value:claims)
    result=client.post("/v1/auth/google/",{"credential":"mock","challenge_id":challenge["challenge_id"]},format="json")
    assert result.status_code==403
    assert not GoogleIdentity.objects.exists()


def test_trial_admin_login_logout_never_touches_personal_credential(user, trial):
    from unittest.mock import patch
    trial.LOCAL_EXECUTION=True
    client=APIClient()
    with patch("desktop.credentials.remember_owner_token") as remember, patch("desktop.credentials.forget_owner_token") as forget:
        response=client.post("/v1/auth/login",{"username":user.username,"password":"testing-a-long-password"},format="json")
        assert response.status_code==200
        client.credentials(HTTP_AUTHORIZATION="Token " + response.data["token"])
        assert client.post("/v1/auth/logout").status_code==200
        remember.assert_not_called();forget.assert_not_called()


def test_open_signup_cap_and_returning_login(trial, monkeypatch):
    from assistant import auth_views
    trial.TEST_OPEN_SIGNUP = True
    trial.TEST_INVITED_EMAILS = set()
    trial.GOOGLE_SIGN_IN_CLIENT_ID = "trial.apps.googleusercontent.com"
    def login(subject):
        client = APIClient()
        challenge = client.post("/v1/auth/google/challenge/", {}, format="json").data
        claims = {"iss":"https://accounts.google.com", "aud":trial.GOOGLE_SIGN_IN_CLIENT_ID,
                  "sub":subject, "email":subject+"@gmail.com", "email_verified":True, "nonce":challenge["nonce"]}
        monkeypatch.setattr(auth_views, "verify_google_credential", lambda value: claims)
        return client.post("/v1/auth/google/", {"credential":"mock", "challenge_id":challenge["challenge_id"]}, format="json")
    from django.core.cache import cache
    for i in range(10):
        cache.clear()
        assert login(str(i)).status_code == 200
    cache.clear()
    assert login("extra").status_code == 403
    assert GoogleIdentity.objects.count() == 10
    cache.clear()
    result = login("0")
    assert result.status_code == 200
    assert result.data["is_admin"] is False
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token " + result.data["token"])
    assert client.get("/v1/conversations/").status_code == 200
    assert client.get("/v1/admin/analytics/").status_code == 403


def test_trial_reports_and_settings_are_personal(client, user, trial):
    from assistant.models import Report
    other = get_user_model().objects.create_user("foreign")
    own = Report.objects.create(user=user, title="mine")
    foreign = Report.objects.create(user=other, title="private")
    listing = client.get("/v1/reports/")
    assert listing.status_code == 200
    assert [r["title"] for r in listing.data] == ["mine"]
    assert client.get(f"/v1/reports/{foreign.pk}/detail/").status_code == 404
    assert client.delete(f"/v1/reports/{foreign.pk}/").status_code == 404
    assert client.post(f"/v1/reports/{own.pk}/deliver/", {}, format="json").status_code == 403
    assert client.patch("/v1/preferences/", {"response_detail":"brief"}, format="json").status_code == 200
    assert client.patch("/v1/preferences/", {"interactive_profile":"gemini"}, format="json").status_code == 400
    assert client.get("/v1/memories/").status_code == 200
    assert client.post("/v1/control/pause/", {}, format="json").status_code == 403


def test_trial_voice_transcribes_without_native_access(client, user, trial):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from unittest.mock import patch
    with patch("assistant.integrations.voice.transcribe_audio", return_value="spoken hello") as transcribe:
        result = client.post("/v1/turn", {"audio":SimpleUploadedFile("note.webm", b"sample", content_type="audio/webm"), "request_id":"voice-test"}, format="multipart")
    assert result.status_code == 200
    transcribe.assert_called_once()
    assert client.post("/v1/local/voice/", {}, format="json").status_code == 403


def test_trial_report_worker_executes_without_owner_tools(user, trial):
    from assistant.models import Report
    from assistant import tasks
    from unittest.mock import patch
    report = Report.objects.create(user=user, title="test research")
    with patch("assistant.tasks.build_report", return_value={"report_id":str(report.pk)}) as build, patch("assistant.tasks.deliver_report_file") as delivery:
        tasks.research_report.run(str(report.pk))
    build.assert_called_once()
    # delivery helper retains its explicit no-host permission guard.
    delivery.assert_called_once()


def test_trial_report_creation_is_bounded_and_replay_safe(client, user, trial):
    from unittest.mock import patch
    payload = {"topic":"safe report", "request_id":"report-one"}
    with patch("assistant.views.kick"):
        first = client.post("/v1/reports/", payload, format="json")
        assert first.status_code == 202
        assert client.post("/v1/reports/", payload, format="json").status_code == 200
        assert client.post("/v1/reports/", {"topic":"another report", "request_id":"report-two"}, format="json").status_code == 400
