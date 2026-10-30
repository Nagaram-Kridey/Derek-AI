import io
import json
from unittest.mock import patch
from django.core.management import call_command
from assistant.model_evaluation import CASES, diagnostics


def test_diagnostics_do_not_retain_generated_content():
    text = 'private-marker transaction ' + 'word ' * 110
    metrics = diagnostics(CASES[3], {'text': text, 'tool_calls': [{'secret': 'private-marker'}]})
    assert metrics['length_in_range']
    assert metrics['missing_concepts'] == ['rollback', 'isolation']
    assert metrics['has_tool_calls']
    assert 'private-marker' not in json.dumps(metrics)


def test_benchmark_checkpoints_survive_interruption(user, tmp_path):
    output = tmp_path / 'metrics.json'
    stream = io.StringIO()
    with patch('assistant.management.commands.evaluate_models.BudgetGateway') as gateway:
        gateway.return_value.chat.side_effect = [{'text': '1290 1010'}, KeyboardInterrupt()]
        try:
            call_command('evaluate_models', user_id=user.pk, provider=['freellmapi'], repeat=1,
                         output=output, stdout=stream)
        except KeyboardInterrupt:
            pass
    saved = json.loads(output.read_text())
    assert saved['complete'] is False
    assert len(saved['samples']) == 1
    assert saved['samples'][0]['passed']
    assert saved['samples'][0]['diagnostics']['word_count'] == 2
