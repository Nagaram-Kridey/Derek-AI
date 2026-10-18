from datetime import timedelta
from unittest.mock import patch
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from assistant import commands, models as m, services
from assistant.tasks import process_command, tick


@pytest.fixture(autouse=True)
def no_dispatch():
    with (
        patch("assistant.command_views.kick"),
        patch("assistant.commands.kick"),
        patch("assistant.services.kick"),
        patch("assistant.tasks.kick"),
        patch("assistant.views.kick"),
    ):
        yield


def reminder(user, **options):
    command, _ = commands.submit(
        user, "Please prepare a reminder", request_id=str(uuid.uuid4()), **options
    )
    args = {
        "name": "Water",
        "kind": "reminder",
        "payload": {"message": "Drink water"},
        "schedule": {
            "kind": "once",
            "at": (timezone.now() + timedelta(hours=1)).isoformat(),
        },
    }
    with patch("assistant.services.BudgetGateway") as gateway:
        gateway.return_value.chat.return_value = {
            "tool_calls": [{"name": "schedule_task", "args": args}]
        }
        process_command(str(command.pk))
    return m.ActionProposal.objects.get(action__command=command)


def test_command_replay_and_changed_payload(client, user):
    body = {"text": "hello", "request_id": str(uuid.uuid4())}
    first = client.post("/v1/commands/", body, format="json")
    second = client.post("/v1/commands/", body, format="json")
    assert first.status_code == second.status_code == 202
    assert first.data["command_id"] == second.data["command_id"]
    assert second["X-Command-Replayed"] == "true"
    changed = client.post(
        "/v1/commands/", {**body, "text": "Different instruction"}, format="json"
    )
    assert changed.status_code == 400 and m.Command.objects.count() == 1


def test_builtin_does_not_infer_and_worker_replay_is_safe(user):
    command, _ = commands.submit(user, "hello")
    with patch("assistant.services.BudgetGateway") as gateway:
        process_command(str(command.pk))
        process_command(str(command.pk))
        gateway.assert_not_called()
    command.refresh_from_db()
    assert (
        command.status == "completed" and command.response["handled_by"] == "built_in"
    )
    assert (
        m.Message.objects.filter(
            conversation=command.conversation, role="assistant"
        ).count()
        == 1
    )


def test_cancel_before_submission_creates_durable_tombstone(client, user):
    request_id = str(uuid.uuid4())
    assert (
        client.post(
            "/v1/commands/cancel/", {"request_id": request_id}, format="json"
        ).status_code
        == 200
    )
    command, _ = commands.submit(user, "Prepare a reminder", request_id=request_id)
    assert command.status == "cancelled"
    with patch("assistant.services.BudgetGateway") as gateway:
        process_command(str(command.pk))
        gateway.assert_not_called()
    assert not m.ActionExecution.objects.exists()


def test_confirmation_is_exact_and_idempotent(client, user):
    proposal = reminder(user)
    assert not m.ScheduledTask.objects.exists()
    url = f"/v1/action-proposals/{proposal.pk}/confirm/"
    body = {"revision": proposal.revision, "payload_digest": proposal.payload_digest}
    assert (
        client.post(url, {**body, "payload_digest": "wrong"}, format="json").status_code
        == 400
    )
    assert (
        client.post(url, {**body, "revision": True}, format="json").status_code == 400
    )
    assert (
        client.post(url, body, format="json").data["proposal"]["status"] == "confirmed"
    )
    assert client.post(url, body, format="json").status_code == 200
    assert m.ScheduledTask.objects.count() == 1


@pytest.mark.parametrize("state", ["expired", "replaced", "paused", "cancelled"])
def test_unavailable_confirmation_cannot_create_task(user, state):
    proposal = reminder(user)
    if state == "expired":
        proposal.expires_at = timezone.now() - timedelta(seconds=1)
        proposal.save()
    elif state == "replaced":
        commands.invalidate_proposals(proposal.action.command.conversation_id)
    elif state == "paused":
        current = services.state(user)
        current.paused = True
        current.save()
    else:
        commands.cancel_request(user, proposal.action.command.request_id)
    try:
        result = commands.decide(
            proposal, True, proposal.revision, proposal.payload_digest
        )
        assert "message" in result
    except ValueError:
        pass
    assert not m.ScheduledTask.objects.exists()


@pytest.mark.parametrize("channel,input_mode", [("telegram", "text"), ("web", "voice")])
def test_unbound_yes_never_confirms(user, channel, input_mode):
    options = {"channel": channel, "input_mode": input_mode}
    if channel == "telegram":
        options["external_key"] = "123"
    proposal = reminder(user, **options)
    command, _ = commands.submit(
        user, "yes", conversation_id=proposal.action.command.conversation_id, **options
    )
    process_command(str(command.pk))
    proposal.refresh_from_db()
    assert proposal.status == "pending" and not m.ScheduledTask.objects.exists()


def test_proposal_expiration_updates_saved_command(user):
    proposal = reminder(user)
    proposal.expires_at = timezone.now() - timedelta(seconds=1)
    proposal.save()
    tick()
    proposal.refresh_from_db()
    assert proposal.status == "expired"
    result = commands.command_data(m.Command.objects.get(pk=proposal.action.command_id))
    assert result["status"] == "completed" and "expired" in result["reply_text"]


def test_new_command_resets_web_conversation(user):
    original, _ = commands.submit(user, "hello")
    command, _ = commands.submit(user, "/new", conversation_id=original.conversation_id)
    assert command.conversation_id != original.conversation_id
    process_command(str(command.pk))
    command.refresh_from_db()
    assert command.status == "completed"


def test_conversation_profile_is_pinned(client, user):
    original, _ = commands.submit(user, "hello", profile="configured")
    assert client.post("/v1/preferences/", {}, format="json").status_code == 405
    response = client.patch(
        "/v1/preferences/", {"interactive_profile": "gemini"}, format="json"
    )
    assert response.status_code == 200
    following, _ = commands.submit(
        user, "what time is it", conversation_id=original.conversation_id
    )
    assert following.model_profile == "configured"
    with pytest.raises(ValueError):
        commands.submit(
            user,
            "change model",
            conversation_id=original.conversation_id,
            profile="gemini",
        )


def test_other_owner_cannot_read_command_or_proposal(client, user):
    other = get_user_model().objects.create_user(username="other", is_active=False)
    proposal = reminder(other)
    assert client.get(f"/v1/commands/{proposal.action.command_id}/").status_code == 404
    assert client.get(f"/v1/action-proposals/{proposal.pk}/").status_code == 404


def test_calendar_timeout_is_not_replayed(user, settings):
    settings.GOOGLE_CLIENT_ID = "test-client"
    settings.GOOGLE_CLIENT_SECRET = "test-secret"
    from cryptography.fernet import Fernet

    settings.CREDENTIAL_ENCRYPTION_KEY = Fernet.generate_key().decode()
    m.ProviderCredential.objects.create(
        user=user, provider="google", ciphertext="test-only"
    )
    command, _ = commands.submit(user, "Prepare a Calendar event")
    action = m.ActionExecution.objects.create(
        user=user,
        command=command,
        step=0,
        tool="calendar_create_event",
        args={
            "summary": "Meeting",
            "start": {"dateTime": "2026-11-01T10:00:00+05:30"},
            "end": {"dateTime": "2026-11-01T11:00:00+05:30"},
        },
        status="pending",
    )
    command.status = "running"
    command.save()
    outcome = commands.prepare(action)
    proposal = m.ActionProposal.objects.get(pk=outcome["proposal"]["id"])
    from assistant.integrations.errors import ProviderError

    with patch(
        "assistant.commands.apply_calendar", side_effect=ProviderError("timeout")
    ) as apply:
        result = commands.decide(
            proposal, True, proposal.revision, proposal.payload_digest
        )
        assert result["status"] == "needs_attention"
        with pytest.raises(ValueError):
            commands.decide(proposal, True, proposal.revision, proposal.payload_digest)
        assert apply.call_count == 1
