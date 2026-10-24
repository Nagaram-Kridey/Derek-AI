"""Owner roadmap: planning state only; never executes prompts or test commands."""
import json
from pathlib import Path
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import RoadmapBoard

STATES = {'implemented', 'in_progress', 'planned', 'idea', 'blocked', 'verified'}


def seed():
    return json.loads(Path(__file__).with_name('roadmap_seed.json').read_text(encoding='utf-8'))


def validate(items):
    if not isinstance(items, list) or len(items) > 200:
        raise ValueError('Use at most 200 roadmap blocks.')
    ids = set()
    fields = {'id', 'title', 'phase', 'origin', 'status', 'difficulty', 'description',
              'evidence', 'next_step', 'owner_action', 'dependencies', 'enabled',
              'test_mode', 'test_result', 'notes', 'priority'}
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError('Invalid roadmap block fields.')
        for key, value in item.items():
            if key == 'enabled':
                if type(value) is not bool:
                    raise ValueError('enabled must be boolean.')
            elif key == 'dependencies':
                if not isinstance(value, list) or len(value) > 30 or any(not isinstance(x, str) for x in value):
                    raise ValueError('Dependencies must be block IDs.')
            elif not isinstance(value, str) or len(value) > 4000:
                raise ValueError('Text fields must be strings of at most 4000 characters.')
        if not item['id'] or item['id'] in ids or not item['title'].strip():
            raise ValueError('Block IDs must be unique and titles are required.')
        ids.add(item['id'])
        if item['status'] not in STATES or item['test_mode'] not in {'isolated', 'live', 'none'} or item['test_result'] not in {'not_run', 'queued', 'passed', 'failed'}:
            raise ValueError('Invalid status or test selection.')
        if item['priority'] not in {'now', 'next', 'later'} or item['difficulty'] not in {'low', 'medium', 'high', 'very_high'}:
            raise ValueError('Invalid priority or difficulty.')
        if (item['status'] == 'verified' or item['test_result'] == 'passed') and not item['evidence'].strip():
            raise ValueError('Record evidence before marking verified or passed.')
    graph = {i['id']: i['dependencies'] for i in items}
    visited = set()
    def visit(key, path):
        if key not in ids or key in path:
            raise ValueError('Dependencies must exist and cannot form cycles.')
        if key in visited:
            return
        for child in graph[key]:
            visit(child, path | {key})
        visited.add(key)
    for key in ids:
        visit(key, set())


@api_view(['GET', 'PUT'])
def board(request):
    row, _ = RoadmapBoard.objects.get_or_create(user=request.user, defaults={'items': seed()})
    if request.method == 'PUT':
        try:
            if set(request.data) != {'version', 'items'} or type(request.data['version']) is not int:
                raise ValueError('Send items and the version you edited.')
            validate(request.data['items'])
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=400)
        with transaction.atomic():
            # Compare-and-swap also protects SQLite writers and stale browser tabs.
            changed = RoadmapBoard.objects.filter(pk=row.pk, version=request.data['version']).update(
                items=request.data['items'], version=request.data['version'] + 1)
            if not changed:
                return Response({'detail': 'Roadmap changed elsewhere. Reload before saving.'}, status=409)
            from .utils import audit
            audit(request.user, 'roadmap.updated', version=request.data['version'] + 1, blocks=len(request.data['items']))
        row.refresh_from_db()
    return Response({'version': row.version, 'items': row.items})
