"""Opt-in synthetic provider benchmark. Never dispatches tools or sends messages."""
import json
import time
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import override_settings
from assistant.model_evaluation import CASES, diagnostics, score, summarize
from assistant.utils import BudgetGateway
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Benchmark synthetic replies without executing tools; prints safe metrics, never provider error bodies.'

    def add_arguments(self, parser):
        parser.add_argument('--provider', action='append', choices=['gemini', 'ollama', 'freellmapi'])
        parser.add_argument('--repeat', type=int, default=1, choices=range(1, 4))
        parser.add_argument('--user-id', type=int, required=True)
        parser.add_argument('--output', type=Path, help='Save synthetic metrics as JSON; contains no answers or credentials.')

    def handle(self, *args, **options):
        user = get_user_model().objects.get(pk=options['user_id'], is_active=True)
        rows = []
        for provider in dict.fromkeys(options['provider'] or [settings.MODEL_PROVIDER]):
            with override_settings(MODEL_PROVIDER=provider):
                for iteration in range(options['repeat']):
                    for case in CASES:
                        started = time.monotonic()
                        try:
                            result = BudgetGateway(user).chat(case['messages'], [], max_output_tokens=512)
                            passed = bool(score(case, result))
                            error = None
                            metrics = diagnostics(case, result)
                        except Exception:
                            passed, error = False, 'provider_unavailable_or_failed'
                            metrics = {}
                        row = {'provider': provider, 'case': case['id'], 'iteration': iteration,
                               'passed': passed, 'latency_ms': round((time.monotonic()-started)*1000), 'error': error, 'diagnostics': metrics}
                        rows.append(row)
                        self.stdout.write(json.dumps(row))
                        self.stdout.flush()
                        if options.get('output'):
                            output = options['output']
                            output.parent.mkdir(parents=True, exist_ok=True)
                            output.write_text(json.dumps({'samples': rows, 'summary': summarize(rows), 'complete': False}, indent=2), encoding='utf-8')
        summary = summarize(rows)
        self.stdout.write(json.dumps(summary))
        if options.get('output'):
            options['output'].parent.mkdir(parents=True, exist_ok=True)
            options['output'].write_text(json.dumps({'samples': rows, 'summary': summary, 'complete': True}, indent=2), encoding='utf-8')
