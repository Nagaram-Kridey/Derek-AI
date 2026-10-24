from copy import deepcopy
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from assistant.roadmap_views import seed, validate


def test_seed_and_cycle_validation():
    items = seed()
    validate(items)
    items[0]['dependencies'] = [items[1]['id']]
    with pytest.raises(ValueError, match='cycles'):
        validate(items)


def test_owner_board_and_stale_save(client, user):
    first = client.get('/v1/roadmap/').json()
    assert len(first['items']) == 35
    change = deepcopy(first)
    change['items'][0]['notes'] = 'Owner acceptance pending'
    assert client.put('/v1/roadmap/', change, format='json').status_code == 200
    assert client.put('/v1/roadmap/', first, format='json').status_code == 409
    assert client.get('/v1/roadmap/').json()['items'][0]['notes'] == 'Owner acceptance pending'
    other = get_user_model().objects.create_user(username='other')
    client.force_authenticate(other)
    assert client.get('/v1/roadmap/').json()['items'][0]['notes'] == ''
    assert APIClient().get('/v1/roadmap/').status_code in (401, 403)


def test_evidence_required_and_invalid_fields_rejected(client):
    board = client.get('/v1/roadmap/').json()
    board['items'][0].update(status='verified', evidence='')
    assert client.put('/v1/roadmap/', board, format='json').status_code == 400
    board['items'][0]['evidence'] = 'Fixture acceptance, 2026-10-23'
    assert client.put('/v1/roadmap/', board, format='json').status_code == 200
    board = client.get('/v1/roadmap/').json()
    board['items'][0]['execute_shell'] = 'not supported'
    assert client.put('/v1/roadmap/', board, format='json').status_code == 400


def test_test_plan_and_toggle_do_not_create_jobs(client):
    from assistant.models import ScheduledTask, DesktopJob, Workflow
    before = (ScheduledTask.objects.count(), DesktopJob.objects.count(), Workflow.objects.count())
    board = client.get('/v1/roadmap/').json()
    board['items'][0].update(test_result='queued', test_mode='live', enabled=False)
    assert client.put('/v1/roadmap/', board, format='json').status_code == 200
    assert before == (ScheduledTask.objects.count(), DesktopJob.objects.count(), Workflow.objects.count())
