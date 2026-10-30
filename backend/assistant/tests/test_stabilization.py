from types import SimpleNamespace
from unittest.mock import patch
from assistant.whatsapp_intents import route, controls, authorized_direct
from assistant.model_evaluation import CASES, score, summarize


def test_basic_chat_and_exact_send_do_not_query_experimental_tables():
    with patch('assistant.whatsapp_intents.settings_for', side_effect=AssertionError('Dormant schema accessed')):
        assert route(SimpleNamespace(input_text='Explain caching')) is None
        command = SimpleNamespace(input_text='Send a WhatsApp message to Person saying: Hello')
        assert route(command)['tool_calls'][0]['args']['message'] == 'Hello'
        assert not authorized_direct(command, {})
        assert 'deferred' in controls(SimpleNamespace(input_text='watch Person'))


def test_monitor_cannot_claim_watches_or_accept_observations(client):
    from rest_framework.test import APIRequestFactory, force_authenticate
    from assistant.whatsapp_watch import sync, observe
    factory = APIRequestFactory()
    for view, args, status in [(sync, (), 200), (observe, ('unused',), 409)]:
        request = factory.post('/', {}, format='json')
        force_authenticate(request, user=client.handler._force_user)
        response = view(request, *args)
        assert response.status_code == status
        if status == 200:
            assert response.data['watches'] == []
    assert client.post('/v1/whatsapp/', {'direct_send': True}, format='json').status_code == 409


def test_model_quality_gates_precede_latency():
    assert score(CASES[0], {'text': 'Spent 1,290; remaining 1,010.'})
    assert not score(CASES[0], {'text': 'Spent 1200; remaining 1100.'})
    assert not score(CASES[0], {'text': '1290 1010', 'tool_calls': [{'name': 'anything'}]})
    assert score(CASES[2], {'text': "I don't have that information."})
    assert not score(CASES[2], {'text': 'You met at 11:00, I do not know.'})
    result = summarize([{'provider': 'fast', 'passed': False, 'latency_ms': 1},
                        {'provider': 'correct', 'passed': True, 'latency_ms': 100}])
    assert result['recommended_provider'] == 'correct'


def test_project_pipeline_exports_five_ideas_two_shortlisted_with_labels(user, client, settings, tmp_path):
    from assistant import models as m
    from assistant.tasks import research_report
    from docx import Document
    settings.MEDIA_ROOT = tmp_path
    ideas = []
    for number in range(1, 6):
        ideas.append(dict(title=f'Enterprise proposal {number}', target_users='Operations teams',
            problem='Teams need clearer workflows', mvp='Use public synthetic records',
            architecture='Django and PostgreSQL', production_features=['Audit', 'Retry', 'Monitoring'],
            implementation_plan=['Validate', 'Prototype', 'Evaluate'], risks_and_validation='Validate with users',
            business_value=number, feasibility=number, engineering_depth=number, novelty=number,
            evidence_indices=[]))
    base = dict(title='Enterprise software and AI', executive_summary='Synthetic evidence fixture',
                key_findings=[{'text':'An unsupported claim', 'verified':False, 'source_urls':[]}],
                next_steps=[], sources=[], citations=[])
    row = m.Report.objects.create(user=user,title=base['title'],content={'report_kind':'project_ideas'})
    with patch('assistant.tasks.kick'), patch('assistant.integrations.research.run_research',return_value=base), patch('assistant.tasks.BudgetGateway') as gateway:
        gateway.return_value.propose_projects.return_value = {'ideas': ideas}
        research_report(str(row.id))
        research_report(str(row.id))
    row.refresh_from_db()
    assert row.status == 'completed'
    assert len(row.content['project_ideas']) == 5
    assert row.content['shortlisted_projects'] == [5, 4]
    doc = Document(row.docx.path)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'Unverified: An unsupported claim' in text
    assert sum(p.text.startswith('Idea ') for p in doc.paragraphs) == 5
    assert sum(p.text.startswith('Shortlist ') for p in doc.paragraphs) == 2
    for kind, signature in [('pdf', b'%PDF'), ('docx', b'PK')]:
        response = client.get(f'/v1/reports/{row.id}/download/?format={kind}')
        assert response.status_code == 200
        assert b''.join(response.streaming_content).startswith(signature)


def test_idle_worker_claims_jobs_without_optional_monitor_requests():
    from unittest.mock import Mock
    from companion.runner import Worker
    client = Mock()
    client.claim.return_value = None
    worker = Worker(SimpleNamespace(), client, journal=Mock())
    assert worker.once() is False
    client.heartbeat.assert_called_once()
    client.claim.assert_called_once()
    client.post.assert_not_called()
