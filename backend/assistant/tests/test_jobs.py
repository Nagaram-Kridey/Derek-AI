from unittest.mock import patch
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.test import APIClient
import pytest
from assistant import models as m, services
from assistant.tasks import research_report, execute_run

@pytest.fixture(autouse=True)
def no_broker():
    with patch("assistant.services.kick"), patch("assistant.tasks.kick"), patch("assistant.views.kick"):
        yield

def test_research_job_generates_private_downloads(client,user,settings,tmp_path):
    settings.MEDIA_ROOT = tmp_path
    report = m.Report.objects.create(user=user,title="A topic")
    result = {"title":"A topic","executive_summary":"Summary","key_findings":[],"next_steps":[],"sources":[],"citations":[]}
    with patch("assistant.integrations.research.run_research",return_value=result),patch("assistant.tasks.BudgetGateway"):
        research_report(str(report.id))
        research_report(str(report.id))
    report.refresh_from_db()
    assert report.status == "completed" and report.pdf and report.docx
    path = f"/v1/reports/{report.id}/download/?format=pdf"
    assert APIClient().get(path).status_code == 401
    response=client.get(path)
    assert response.status_code == 200
    assert b"".join(response.streaming_content).startswith(b"%PDF")
    assert m.Notification.objects.filter(user=user).count()==1
    assert client.delete(f"/v1/reports/{report.id}/").status_code==204
    assert not list(tmp_path.glob("reports/**/*.pdf"))

def test_cloud_workflow_executes_each_step_once(user):
    workflow=services.enable_workflow(services.create_workflow(user,{"name":"Routine","steps":[{"tool":"notify","args":{"message":"Hello"}}],"allowed_tools":["notify"]}))
    run=services.start_run(workflow)
    execute_run(str(run.id));execute_run(str(run.id))
    run.refresh_from_db()
    assert run.status=="completed" and m.Notification.objects.count()==1

def test_oauth_state_is_one_use_and_token_is_encrypted(client,user,settings):
    settings.GOOGLE_CLIENT_ID="client";settings.GOOGLE_CLIENT_SECRET="secret"
    settings.CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()
    response=client.post("/v1/calendar/connect/")
    state=parse_qs(urlsplit(response.data["url"]).query)["state"][0]
    api=APIClient()
    credentials={"access_token":"private-access-token","refresh_token":"private-refresh","expires_in":3600,"scope":"https://www.googleapis.com/auth/calendar.events.owned"}
    with patch("assistant.integrations.calendar.exchange_code",return_value=credentials):
        assert api.get("/v1/calendar/callback/",{"state":state,"code":"code"}).status_code==200
        assert api.get("/v1/calendar/callback/",{"state":state,"code":"code"}).status_code==400
    row=m.ProviderCredential.objects.get(user=user)
    assert "private-access-token" not in row.ciphertext
    assert services.calendar_token(user)=="private-access-token"

def test_expired_approval_cannot_resume(client,user):
    workflow=services.enable_workflow(services.create_workflow(user,{"name":"Delete note","steps":[{"tool":"file.delete","args":{"path":"C:\\Notes\\note.txt"}}],"allowed_tools":["file.delete"],"allowed_paths":["C:\\Notes"]}))
    run=services.start_run(workflow);run.status="needs_approval";run.save()
    approval=services.request_approval(run,"permanent_delete")
    approval.expires_at=timezone.now()-timedelta(seconds=1);approval.save()
    assert client.post(f"/v1/approvals/{approval.id}/approve/").status_code==400

def test_interrupted_delivery_is_flagged_without_resending(user):
    from assistant.tasks import tick
    row=m.Notification.objects.create(user=user,text="Uncertain reminder",status="sending",started_at=timezone.now()-timedelta(minutes=6))
    tick()
    row.refresh_from_db()
    assert row.status=="needs_attention"
    assert m.Notification.objects.count()==1
