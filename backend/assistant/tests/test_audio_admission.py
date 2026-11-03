from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.response import Response

from assistant import models as m

pytestmark = pytest.mark.django_db


def upload(client):
    return client.post('/v1/turn', {'audio': SimpleUploadedFile('voice.wav', b'not-real-audio', content_type='audio/wav')}, format='multipart')


def test_pending_request_rejected_before_transcription(client, user):
    conversation = m.Conversation.objects.create(user=user, title='Pending')
    m.Command.objects.create(user=user, conversation=conversation, request_id='pending', input_text='x', fingerprint='x', status='queued')
    with patch('assistant.views._turn') as expensive:
        assert upload(client).status_code == 409
        expensive.assert_not_called()


def test_audio_rate_and_global_busy_reject_before_work(client, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    cache.clear()
    with patch('companion.journal.WorkerLock.__enter__', side_effect=RuntimeError('busy')), patch('assistant.views._turn') as expensive:
        assert upload(client).status_code == 409
        expensive.assert_not_called()
    cache.clear()
    with patch('assistant.views._turn', return_value=Response({'ok': True})) as expensive:
        for _ in range(6):
            assert upload(client).status_code == 200
        assert upload(client).status_code == 429
        assert expensive.call_count == 6
    cache.clear()


def test_daily_quota_rejects_audio_before_transcription(client, user, settings):
    settings.DAILY_MODEL_CALL_LIMIT = 1
    m.UsageDay.objects.create(user=user, date=timezone.localdate(), model_calls=1)
    with patch('assistant.views._turn') as expensive:
        assert upload(client).status_code == 429
        expensive.assert_not_called()
