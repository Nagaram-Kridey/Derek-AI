from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from assistant import commands, models as m
from assistant.telegram_buttons import button_data, resolve


@pytest.fixture
def proposal(user):
    command, _ = commands.submit(
        user, "Prepare a reminder", channel="telegram", external_key="123"
    )
    action = m.ActionExecution.objects.create(
        user=user,
        command=command,
        tool="schedule_task",
        step=0,
        status="awaiting_confirmation",
        args={},
    )
    return m.ActionProposal.objects.create(
        user=user,
        action=action,
        readback="Reviewed action",
        payload_digest="payload-binding",
        expires_at=timezone.now() + timedelta(minutes=2),
    )


def test_signed_button_is_compact_and_bound_to_exact_proposal(user, proposal):
    data = button_data(proposal, "y")
    assert len(data.encode()) <= 64
    saved, approved = resolve(user, data)
    assert saved.pk == proposal.pk and approved
    assert resolve(user, button_data(proposal, "n"))[1] is False


@pytest.mark.parametrize("change", ["signature", "revision", "owner", "channel"])
def test_changed_button_cannot_resolve(user, proposal, change):
    data = button_data(proposal, "y")
    owner = user
    if change == "signature":
        data = data[:-1] + ("a" if data[-1] != "a" else "b")
    elif change == "revision":
        proposal.revision += 1
        proposal.save()
    elif change == "owner":
        owner = get_user_model().objects.create_user(username="other", is_active=False)
    else:
        command = proposal.action.command
        command.channel = "web"
        command.save()
    with pytest.raises(ValueError):
        resolve(owner, data)
