from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys

import pytest
from companion.speech import SpeechResult
from companion.voice import VoiceSession
from companion.voice_audio import FRAME_BYTES, UtteranceDetector


@pytest.fixture
def session():
    config = SimpleNamespace(
        voice_barge_in=False, voice_session_seconds=300, voice_idle_seconds=30
    )
    client = Mock(pending_turn=None)
    with (
        patch("companion.voice.Microphone") as microphone,
        patch("companion.voice.UtteranceDetector"),
    ):
        microphone.return_value.stream = None
        current = VoiceSession(
            config, Mock(), client=client, output=Mock(), console=False
        )
        current.job = Mock()
        yield current


def proposal():
    return {
        "id": "proposal-id",
        "revision": 1,
        "payload_digest": "exact-binding",
        "readback": "Create the reviewed reminder",
        "status": "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
    }


def test_window_session_does_not_start_capture_implicitly(session):
    assert not session.active and session.phase == "idle"
    session.microphone.open.assert_not_called()
    with patch("companion.voice.desktop_unlocked", return_value=False):
        session.start()
    session.microphone.open.assert_not_called()


def test_unheard_or_unbound_yes_cannot_authorize(session):
    session.answer({"reply_text": "Review this", "action_proposals": [proposal()]})
    assert session.proposal is None and session.reading_proposal
    session.dispatch("yes")
    session.client.decide_proposal.assert_not_called()
    assert not any(call.args[0] == "decision" for call in session.job.call_args_list)


def test_complete_readback_arms_only_its_exact_proposal(session):
    current = proposal()
    session.active = True
    session.answer({"action_proposals": [current]})
    session.result((session.generation, "speech", SpeechResult(True, None, 1, 0), None))
    assert session.proposal == current
    session.dispatch("confirm")
    kind, decide = session.job.call_args.args
    assert kind == "decision"
    decide()
    session.client.decide_proposal.assert_called_once_with(current, True)
    assert session.proposal is None and session.control_busy


def test_interrupted_readback_is_disarmed(session):
    session.active = True
    session.answer({"action_proposals": [proposal()]})
    session.result(
        (session.generation, "speech", SpeechResult(False, None, 1, 0), None)
    )
    assert session.proposal is None and session.reading_proposal is None
    session.dispatch("yes")
    session.client.decide_proposal.assert_not_called()


def test_expired_readback_and_stale_answer_cannot_arm_confirmation(session):
    expired = proposal()
    expired["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    session.proposal = expired
    session.dispatch("confirm")
    session.client.decide_proposal.assert_not_called()
    session.result(
        (session.generation - 1, "answer", {"action_proposals": [proposal()]}, None)
    )
    assert session.proposal is None and session.reading_proposal is None
    assert session.job.call_args.args[0] == "discard"


@pytest.fixture
def detector(monkeypatch):
    vad = SimpleNamespace(is_speech=lambda frame, _: frame[0] == 1)
    monkeypatch.setitem(sys.modules, "webrtcvad", SimpleNamespace(Vad=lambda _: vad))
    config = SimpleNamespace(
        voice_vad_mode=2, voice_silence_ms=90, voice_max_utterance_seconds=1
    )
    return UtteranceDetector(config)


def test_utterance_detector_ends_after_silence_and_keeps_audio_in_memory(detector):
    voiced, silent = bytes([1]) * FRAME_BYTES, bytes(FRAME_BYTES)
    events = [detector.push(voiced) for _ in range(11)]
    assert any(event.started for event in events)
    for _ in range(3):
        result = detector.push(silent)
    assert result.ended and isinstance(result.audio, bytes)
    assert not detector.started


def test_utterance_detector_bounds_recording_and_rejects_bad_frames(detector):
    with pytest.raises(RuntimeError):
        detector.push(b"bad-frame")
    for _ in range(detector.max_frames):
        result = detector.push(bytes([1]) * FRAME_BYTES)
    assert result.ended and result.limit_reached


def test_utterance_detector_discards_tiny_audio(detector):
    for _ in range(3):
        detector.push(bytes([1]) * FRAME_BYTES)
    assert detector.finish().audio is None
