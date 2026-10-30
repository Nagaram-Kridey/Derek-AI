import pytest
from desktop.message_guard import MessageGuard


def observation(**changes):
    return dict(recipient='MSV Krishna', anchor='intro-1', bubble_id='reply-1',
                incoming=True, below_anchor=True, at_bottom=True,
                stable_scope=True, now=102, **changes)


def guard():
    value = MessageGuard('MSV Krishna', 'Hello')
    value.confirm_outgoing('intro-1', exact_message=True, outgoing=True, now=100)
    return value


def test_reply_requires_two_observations_and_acknowledges_once():
    value = guard()
    assert not value.observe_reply(**observation())
    assert value.observe_reply(**observation())
    assert not value.observe_reply(**observation())


@pytest.mark.parametrize('field,value', [
    ('recipient', 'Other'), ('anchor', 'old'), ('bubble_id', ''),
    ('incoming', False), ('below_anchor', False), ('at_bottom', False),
    ('stable_scope', False), ('now', 400),
])
def test_ambiguous_or_expired_observations_never_acknowledge(field, value):
    state = guard()
    evidence = observation()
    evidence[field] = value
    assert not state.observe_reply(**evidence)
    assert not state.observe_reply(**evidence)


def test_composer_needs_full_exact_text_and_recipient():
    state = guard()
    evidence = dict(recipient='MSV Krishna', unique=True, text='Hello',
                    foreground=True, scope_valid=True, draft_empty=True)
    assert state.verify_composer(**evidence)
    for field, value in [('text', 'Hell'), ('recipient', 'MSV Krishna Jr'),
                         ('foreground', False), ('scope_valid', False),
                         ('draft_empty', False), ('unique', False)]:
        assert not state.verify_composer(**{**evidence, field: value})


def test_control_characters_and_duplicate_outgoing_are_rejected():
    with pytest.raises(ValueError):
        MessageGuard('Recipient', 'Hello\nSend')
    with pytest.raises(ValueError):
        guard().confirm_outgoing('again', exact_message=True, outgoing=True)
