"""Synthetic, tool-free route checks; correctness gates precede latency ranking."""
import re
from statistics import median

CASES = [
    {'id': 'arithmetic', 'messages': [{'role': 'user', 'content': 'Budget 2300. Notebooks cost 870 and pens 420. Give total spent and money remaining.'}], 'numbers': ['1290', '1010']},
    {'id': 'context', 'messages': [
        {'role': 'user', 'content': 'Budget 2300. Notebooks 870, pens 420.'},
        {'role': 'assistant', 'content': 'Spent 1290; remaining 1010.'},
        {'role': 'user', 'content': 'Add folders costing 180. Give new total and remaining budget.'}], 'numbers': ['1470', '830']},
    {'id': 'uncertainty', 'messages': [{'role': 'user', 'content': 'What exact time did I meet my friend yesterday? No meeting details have been provided. Do not guess.'}], 'uncertainty': True},
    {'id': 'explanation', 'messages': [{'role': 'user', 'content': 'Explain database transactions, rollback and isolation with a concrete example. Give 120 to 220 words.'}], 'explanation': True},
]


def score(case, result):
    text = result.get('text', '')
    if not isinstance(text, str) or not text.strip() or result.get('tool_calls'):
        return False
    numbers = re.sub(r'(?<=\d),(?=\d)', '', text)
    if case.get('numbers'):
        return all(re.search(r'(?<!\d)' + number + r'(?!\d)', numbers) for number in case['numbers'])
    if case.get('uncertainty'):
        return bool(re.search(r"don't know|do not know|don.t have|do not have|cannot|can.t|unable|not (?:have|provided|enough)|no (?:meeting|details|information)|haven.t|haven.t been|not been provided", text, re.I)) and not re.search(r'\b\d{1,2}:\d{2}\b', text)
    return 100 <= len(text.split()) <= 260 and all(word in text.lower() for word in ('transaction', 'rollback', 'isolation'))


def diagnostics(case, result):
    """Return only bounded structural metrics, never model text or tool arguments."""
    text = result.get('text', '')
    valid = isinstance(text, str)
    metrics = {'word_count': min(len(text.split()), 100000) if valid else 0,
               'has_final_text': bool(valid and text.strip()),
               'has_tool_calls': bool(result.get('tool_calls'))}
    if case.get('explanation'):
        metrics['missing_concepts'] = [term for term in ('transaction', 'rollback', 'isolation')
                                       if not valid or term not in text.lower()]
        metrics['length_in_range'] = 100 <= metrics['word_count'] <= 260
    return metrics


def summarize(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row['provider'], []).append(row)
    summary = []
    for provider, items in groups.items():
        passed = all(x['passed'] for x in items)
        summary.append({'provider': provider, 'passed': passed, 'cases': len(items),
                        'median_ms': median(x['latency_ms'] for x in items)})
    eligible = [x for x in summary if x['passed']]
    return {'routes': summary, 'recommended_provider': min(eligible, key=lambda x:x['median_ms'])['provider'] if eligible else None,
            'limitation': 'Synthetic smoke checks only; technical factual accuracy and live channel/action acceptance require separate evidence.'}
