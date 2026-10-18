from unittest.mock import patch
import uuid

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from assistant import models as m, services
from assistant.integrations.errors import ProviderError, RequestCancelled
from assistant.integrations.telegram import TelegramRateLimit
from assistant.tasks import send_report_file, execute_run, deliver_command


@pytest.fixture(autouse=True)
def no_dispatch():
    with (
        patch("assistant.views.kick"),
        patch("assistant.tasks.kick"),
        patch("assistant.services.kick"),
    ):
        yield


def task_body():
    return {
        "request_id": str(uuid.uuid4()),
        "name": "Daily water",
        "kind": "reminder",
        "payload": {"message": "Drink water"},
        "schedule": {"kind": "daily", "time": "11:00", "timezone": "Asia/Kolkata"},
    }


def test_form_retry_does_not_duplicate_and_rejects_changed_values(client):
    body = task_body()
    first = client.post("/v1/tasks/", body, format="json")
    again = client.post("/v1/tasks/", body, format="json")
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.data["id"] == again.data["id"]
    assert (
        client.post(
            "/v1/tasks/", {**body, "name": "Different"}, format="json"
        ).status_code
        == 400
    )
    assert m.ScheduledTask.objects.count() == 1
    client.delete(f"/v1/tasks/{first.data['id']}/")
    assert client.post("/v1/tasks/", body, format="json").status_code == 400
    assert not m.ScheduledTask.objects.exists()


def test_schedule_edit_conflict_and_pause_cancels_pending_occurrence(client, user):
    row = services.create_task(user, task_body())
    revision = client.get(f"/v1/tasks/{row.pk}/").data["revision"]
    occurrence = m.ScheduledOccurrence.objects.create(
        task=row, scheduled_for=timezone.now()
    )
    assert (
        client.patch(
            f"/v1/tasks/{row.pk}/",
            {"name": "Updated", "expected": revision},
            format="json",
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/v1/tasks/{row.pk}/",
            {"name": "Stale", "expected": revision},
            format="json",
        ).status_code
        == 409
    )
    occurrence.refresh_from_db()
    assert occurrence.status == "cancelled"


def test_notification_read_and_export_are_owner_scoped(client, user):
    notice = m.Notification.objects.create(user=user, text="Update")
    assert client.post(f"/v1/notifications/{notice.pk}/read/").status_code == 200
    notice.refresh_from_db()
    assert notice.read_at is not None
    m.ProviderCredential.objects.create(
        user=user, provider="google", ciphertext="secret-not-in-export"
    )
    exported = client.get("/v1/export/")
    assert exported.status_code == 200 and exported.data["notifications"][0][
        "id"
    ] == str(notice.pk)
    assert "secret-not-in-export" not in str(exported.data)
    for key in (
        "command_events",
        "workflow_runs",
        "occurrences",
        "preferences",
        "schema_version",
    ):
        assert key in exported.data


def report(user):
    row = m.Report.objects.create(
        user=user,
        title="Saved research",
        status="completed",
        progress={
            "telegram_delivery": {
                "status": "pending",
                "due_at": timezone.now().isoformat(),
            }
        },
    )
    row.pdf.save("test.pdf", ContentFile(b"%PDF-test"))
    return row


@pytest.mark.parametrize("outcome", ["success", "rate_limit", "unknown"])
def test_report_delivery_claims_once_and_never_repeats_unknown(user, settings, outcome):
    settings.TELEGRAM_BOT_TOKEN = "123:test-token"
    settings.TELEGRAM_CHAT_ID = "123"
    row = report(user)
    with patch("assistant.integrations.telegram.send_document") as send:
        send.return_value = {"message_id": 9}
        if outcome == "rate_limit":
            send.side_effect = TelegramRateLimit(60)
        elif outcome == "unknown":
            send.side_effect = ProviderError("Uncertain timeout")
        send_report_file(str(row.pk))
        send_report_file(str(row.pk))
        assert send.call_count == 1
    row.refresh_from_db()
    expected = {
        "success": "sent",
        "rate_limit": "pending",
        "unknown": "needs_attention",
    }[outcome]
    assert row.progress["telegram_delivery"]["status"] == expected


def test_extra_report_copy_requires_explicit_intent(client, user, settings):
    settings.TELEGRAM_BOT_TOKEN = "123:test-token"
    settings.TELEGRAM_CHAT_ID = "123"
    row = report(user)
    row.progress = {"telegram_delivery": {"status": "needs_attention"}}
    row.save()
    url = f"/v1/reports/{row.pk}/deliver/"
    assert client.post(url, {}, format="json").status_code == 400
    assert client.post(url, {"confirm_copy": True}, format="json").status_code == 202
    assert client.post(url, {"confirm_copy": True}, format="json").status_code == 409


def test_cancelled_workflow_cannot_publish_research(user):
    workflow = services.enable_workflow(
        services.create_workflow(
            user,
            {
                "name": "Research",
                "steps": [{"tool": "research.run", "args": {"topic": "Queues"}}],
                "allowed_tools": ["research.run"],
            },
        )
    )
    run = services.start_run(workflow)

    def cancelled_research(*args, **kwargs):
        m.WorkflowRun.objects.filter(pk=run.pk).update(status="cancelled")
        return {"citations": [], "title": "Queues"}

    with (
        patch(
            "assistant.integrations.research.run_research",
            side_effect=cancelled_research,
        ),
        patch("assistant.tasks.BudgetGateway"),
        patch("assistant.integrations.docs.generate_report") as generate,
    ):
        execute_run(str(run.pk))
        generate.assert_not_called()
    assert m.Report.objects.get(user=user).status == "cancelled"
    assert not m.Report.objects.get(user=user).pdf


def test_cancelled_report_aborts_publication(client, user):
    row = m.Report.objects.create(user=user, title="Research", status="running")
    assert client.post(f"/v1/reports/{row.pk}/cancel/").status_code == 200
    from assistant.tasks import build_report

    with pytest.raises(RequestCancelled):
        build_report(row)


def test_telegram_messages_preserve_order_and_uncertainty(user, settings):
    from assistant.commands import submit

    command, _ = submit(user, "hello")
    first = m.Delivery.objects.create(
        user=user,
        command=command,
        destination="123",
        text="First",
        position=0,
        status="needs_attention",
    )
    second = m.Delivery.objects.create(
        user=user, command=command, destination="123", text="Second", position=1
    )
    with patch("assistant.integrations.telegram.send_message") as send:
        deliver_command(str(second.pk))
        send.assert_not_called()
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.status == first.status == "needs_attention"


def test_api_responses_do_not_cache_private_records(client):
    response = client.get("/v1/status/")
    assert response["Cache-Control"] == "no-store, private"
    assert "Authorization" in response["Vary"]


@pytest.mark.parametrize(
    "changes",
    [{"chat_type": "group"}, {"sender": 999}, {"is_bot": True}, {"chat_id": 999}],
)
def test_telegram_rejects_foreign_identity(settings, changes):
    from assistant.telegram_ingress import accepted_payload

    settings.TELEGRAM_CHAT_ID = settings.TELEGRAM_USER_ID = "123"
    values = {
        "chat_type": "private",
        "sender": 123,
        "chat_id": 123,
        "is_bot": False,
        **changes,
    }
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": values["chat_id"], "type": values["chat_type"]},
            "from": {"id": values["sender"], "is_bot": values["is_bot"]},
            "text": "Hello",
        },
    }
    assert accepted_payload(update) is None


def test_partial_telegram_message_is_not_retryable():
    from assistant.integrations.telegram import send_message

    with patch(
        "assistant.integrations.telegram._call",
        side_effect=[{"message_id": 1}, TelegramRateLimit(30)],
    ):
        with pytest.raises(ProviderError) as error:
            send_message("123:test-token", "123", "x" * 5000)
    assert not isinstance(error.value, TelegramRateLimit)
