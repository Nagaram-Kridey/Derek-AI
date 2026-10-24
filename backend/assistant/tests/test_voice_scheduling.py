from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from assistant import commands, models as m
from assistant.schedule_intents import guard_unrecorded_claim, route
from assistant.tasks import process_command
from companion.speech import SpeechResult
from companion.voice import VoiceSession


@pytest.mark.parametrize("text,kind,message", [
    ("Remind me to drink water tomorrow at 9 pm", "once", "drink water"),
    ("Remind me at 9pm tomorrow to drink water", "once", "drink water"),
    ("Set a reminder to stretch every day at 11 am", "daily", "stretch"),
    ("Please remind me to drink water in an hour", "once", "drink water"),
])
def test_spoken_reminder_routes_without_inference(text, kind, message, settings):
    settings.TIME_ZONE = "Asia/Kolkata"
    tool = route(SimpleNamespace(input_text=text))["tool_calls"][0]
    assert tool["name"] == "schedule_task"
    assert tool["args"]["schedule"]["kind"] == kind
    assert tool["args"]["schedule"]["timezone"] == "Asia/Kolkata"
    assert tool["args"]["payload"]["message"] == message


@pytest.mark.parametrize("text", [
    "Don't remind me tomorrow at 9pm", "Remind me tomorrow at 9pm and 10pm to stretch",
    "Remind me to stretch daily starting tomorrow at 9pm",
    "Remind me to stretch Monday at 9pm", "Remind me to stretch tomorrow at 9pm UTC",
    "Remind me to stretch at 9pm", "Open a YouTube channel daily at 9pm",
])
def test_ambiguous_spoken_schedule_stays_with_typed_model(text):
    assert route(SimpleNamespace(input_text=text)) is None


def test_daily_browser_request_uses_valid_disabled_draft(settings):
    from assistant.contracts import validate_workflow
    settings.TIME_ZONE = "Asia/Kolkata"
    args = route(SimpleNamespace(input_text="Open the home youtube page at 9pm everyday."))["tool_calls"][0]["args"]
    cleaned = validate_workflow(args)
    assert cleaned["trigger"]["time"] == "21:00"
    assert cleaned["steps"][0]["args"]["actions"][0]["type"] == "navigate"


def test_unrecorded_scheduling_claim_is_not_presented_as_success():
    assert guard_unrecorded_claim("I've set a reminder for tonight", "Set it at 9pm today").startswith("No scheduling change")
    assert guard_unrecorded_claim("What time should I use?", "Set a reminder") == "What time should I use?"


@pytest.mark.parametrize("affirmative", ["confirm", "yeah", "go ahead"])
def test_voice_confirmation_persists_exactly_one_reminder(client, user, settings, affirmative):
    settings.TIME_ZONE = "Asia/Kolkata"
    with patch("assistant.commands.kick"), patch("assistant.services.kick"), patch("assistant.services.BudgetGateway") as model:
        command, _ = commands.submit(user, "Remind me to drink water tomorrow at 11 am", input_mode="voice")
        process_command(str(command.pk))
        model.assert_not_called()
    proposal = m.ActionProposal.objects.get(action__command=command)
    assert not m.ScheduledTask.objects.exists()
    control = Mock(pending_turn=None)
    control.decide_proposal.side_effect = lambda p, approve: client.post(
        f"/v1/action-proposals/{p['id']}/{'confirm' if approve else 'cancel'}/",
        {"revision": p["revision"], "payload_digest": p["payload_digest"]}, format="json").data
    config = SimpleNamespace(voice_barge_in=False, voice_session_seconds=300, voice_idle_seconds=30)
    with patch("companion.voice.Microphone"), patch("companion.voice.UtteranceDetector"):
        session = VoiceSession(config, Mock(), client=control, output=Mock(), console=False)
        session.job = Mock()
        session.active = True
        data = commands.proposal_data(proposal)
        session.answer({"action_proposals": [data]})
        assert session.proposal is None
        session.result((session.generation, "speech", SpeechResult(True, None, 1, 0), None))
        session.dispatch(affirmative)
        kind, confirm = session.job.call_args.args
        assert kind == "decision"
        saved = confirm()
        assert saved["proposal"]["status"] == "confirmed"
        assert m.ScheduledTask.objects.get(pk=saved["task_id"]).payload == {"message": "drink water"}
        repeated = control.decide_proposal(data, True)
        assert repeated["task_id"] == saved["task_id"]
        assert m.ScheduledTask.objects.count() == 1


def test_past_time_does_not_create_a_task_or_claim_success(user, settings):
    settings.TIME_ZONE = "Asia/Kolkata"
    with patch("assistant.commands.kick"), patch("assistant.services.kick"), patch("assistant.schedule_intents.timezone.now", return_value=datetime(2026, 10, 20, 18, tzinfo=dt_timezone.utc)):
        command, _ = commands.submit(user, "Remind me to stretch today at 9pm", input_mode="voice")
        process_command(str(command.pk))
    command.refresh_from_db()
    assert command.status == "failed"
    assert not m.ScheduledTask.objects.exists() and not m.ActionProposal.objects.exists()
