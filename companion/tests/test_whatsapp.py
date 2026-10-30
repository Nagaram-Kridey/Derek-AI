from unittest.mock import Mock, patch
import pytest
from desktop.visual_text import TextBox
from companion.policy import AttentionRequired
from companion.whatsapp import send_current, layout

MESSAGE = "Hi MSV Krishna, I am Derek, Kridey's Personal Agent. Do you have any queries you want to schedule with Kridey."
ARGS = {'recipient': 'MSV Krishna', 'message': MESSAGE}


def test_focus_refusal_uses_only_fixed_package_launcher():
    from types import SimpleNamespace
    from companion.whatsapp import open_whatsapp, WHATSAPP_APP_ID
    pytest.importorskip('win32gui')
    with patch('companion.whatsapp.whatsapp_windows',return_value=[SimpleNamespace(hwnd=123)]), \
         patch('companion.whatsapp.validate_scope'),patch('desktop.observation.unlocked',return_value=True), \
         patch('win32gui.ShowWindow'),patch('win32gui.SetForegroundWindow',side_effect=RuntimeError()), \
         patch('win32gui.GetForegroundWindow',side_effect=[0,123,123]), \
         patch('subprocess.Popen') as launch:
        open_whatsapp()
    assert launch.call_args.args[0][1]=='shell:AppsFolder\\'+WHATSAPP_APP_ID
    assert launch.call_args.kwargs['shell'] is False


def frame(composer='Type a message', sent=False, header='MSV Krishna'):
    result = [TextBox(header, 515, 60, 110, 20), TextBox(composer, 550, 985, 1100, 20)]
    if sent:
        result.append(TextBox(MESSAGE+' 15:30', 1100, 900, 750, 20, 'outgoing_green'))
    return result


def adapter(*frames):
    value = Mock(bounds=(0, 0, 1920, 1032))
    # Dedicated contact results are under a Chats section; other mentions do
    # not become selectable recipients merely because the text matches.
    frames=[([TextBox('Chats',85,200,45,18)]+list(f)) if any(
        b.text.startswith('MSV Krishna') and b.left<450 and b.top==230 for b in f) else f for f in frames]
    value.observe.side_effect = list(frames)
    return value


def test_exact_readback_before_send_and_outgoing_receipt():
    value = adapter(frame(), frame(), frame(MESSAGE), frame(sent=True))
    pending = Mock()
    with patch('companion.whatsapp.time.sleep'):
        result = send_current(ARGS, before_mutation=pending, adapter_factory=lambda _: value)
    pending.assert_called_once_with(0)
    assert value.keys.call_args_list[0].args == (MESSAGE,)
    assert value.keys.call_args_list[1].args == ()
    assert result['outgoing_verified'] and not result['delivery_verified']
    value.close.assert_called_once()


@pytest.mark.parametrize('first', [frame('Existing draft'), frame(header='MSV Krishna Jr')])
def test_wrong_recipient_and_existing_drafts_never_mutate(first):
    value = adapter(first)
    pending = Mock()
    with pytest.raises(AttentionRequired):
        send_current(ARGS, before_mutation=pending, adapter_factory=lambda _: value)
    pending.assert_not_called()
    value.keys.assert_not_called()


def test_bad_composed_text_is_left_unsent():
    value = adapter(frame(), frame(), frame('Hi MSV Krishna'))
    with patch('companion.whatsapp.time.sleep'), pytest.raises(AttentionRequired, match='draft'):
        send_current(ARGS, before_mutation=Mock(), adapter_factory=lambda _: value)
    assert value.keys.call_count == 1


@pytest.mark.parametrize('changed', [frame('Existing draft'), frame(header='Wrong contact')])
def test_post_click_frame_is_verified_before_typing(changed):
    value=adapter(frame(),changed,changed,changed,changed)
    with pytest.raises(AttentionRequired):
        send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:value)
    value.keys.assert_not_called()


def test_caret_ocr_artifact_only_allowed_after_proven_empty_composer():
    value=adapter(frame(),frame('Itype a message'),frame(MESSAGE),frame(sent=True))
    with patch('companion.whatsapp.time.sleep'):
        assert send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:value)['outgoing_verified']
    initial=adapter(*[frame('Itype a message') for _ in range(6)])
    with patch('companion.whatsapp.time.sleep'), pytest.raises(AttentionRequired):
        send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:initial)
    initial.keys.assert_not_called()


def test_search_autofocus_caret_waits_for_exact_empty_frame_before_typing():
    value=adapter(frame('tType a message'),frame('tType a message'),frame(),
                  frame('tType a message'),frame(MESSAGE),frame(sent=True))
    with patch('companion.whatsapp.time.sleep'):
        result=send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:value)
    assert result['outgoing_verified']
    assert value.keys.call_args_list[0].args == (MESSAGE,)
    assert value.click.call_args.args[1] == (1032-90+1032-5)/2


def test_real_draft_appearing_during_caret_retry_is_preserved():
    value=adapter(frame('tType a message'),frame('My existing draft'))
    pending=Mock()
    with patch('companion.whatsapp.time.sleep'),pytest.raises(AttentionRequired):
        send_current(ARGS,before_mutation=pending,adapter_factory=lambda _:value)
    value.keys.assert_not_called()
    value.click.assert_not_called()
    pending.assert_not_called()


def test_incoming_quote_or_old_position_is_not_an_outgoing_receipt():
    from companion.whatsapp import outgoing_receipt
    for box in [TextBox(MESSAGE,1100,900,750,20),
                TextBox(MESSAGE,500,900,750,20,'outgoing_green'),
                TextBox(MESSAGE,1100,200,750,20,'outgoing_green'),
                TextBox('Quoted '+MESSAGE,1100,900,750,20,'outgoing_green')]:
        assert not outgoing_receipt([box],MESSAGE,1920,1032)


def test_send_without_receipt_stays_uncertain_and_never_retries():
    value = adapter(frame(), frame(), frame(MESSAGE), *[frame() for _ in range(5)])
    with patch('companion.whatsapp.time.sleep'), pytest.raises(AttentionRequired, match='uncertain'):
        send_current(ARGS, before_mutation=Mock(), adapter_factory=lambda _: value)
    assert value.keys.call_count == 2


def test_narrow_or_ambiguous_layout_is_rejected():
    with pytest.raises(AttentionRequired):
        layout(frame(), 800, 600, 'MSV Krishna')
    with pytest.raises(AttentionRequired):
        layout(frame()+[TextBox('MSV Krishna', 700, 60, 100, 20)], 1920, 1032, 'MSV Krishna')


def test_registered_workflow_tool_is_typed_and_rejects_control_characters():
    from backend.assistant.contracts import SCHEMAS, DESKTOP_TOOLS
    assert 'desktop.whatsapp' in DESKTOP_TOOLS
    assert SCHEMAS['desktop.whatsapp'].model_validate(ARGS).message == MESSAGE
    with pytest.raises(ValueError):
        SCHEMAS['desktop.whatsapp'].model_validate({**ARGS, 'message': 'Hello\nSend'})


def test_whatsapp_workflows_are_manual_and_single_send():
    from backend.assistant.contracts import validate_workflow
    spec={'allowed_tools':['desktop.whatsapp'], 'allowed_domains':[], 'allowed_paths':[],
          'steps':[{'tool':'desktop.whatsapp','args':ARGS}], 'trigger':{'kind':'manual'}}
    assert validate_workflow(spec)['steps'][0]['args']=={**ARGS,'open_and_search':False,'transport':'native'}
    with pytest.raises(ValueError,match='manually reviewed'):
        validate_workflow({**spec,'steps':spec['steps']*2})
    with pytest.raises(ValueError,match='manually reviewed'):
        validate_workflow({**spec,'trigger':{'kind':'daily','time':'11:00'}})


def test_worker_never_replays_uncertain_native_send(tmp_path):
    from types import SimpleNamespace
    from companion.runner import Worker
    from companion.journal import Journal
    job = {'id': 'wa-fixture', 'tool': 'desktop.whatsapp', 'args': ARGS,
           'policy': {'allowed_tools': ['desktop.whatsapp']}}
    journal = Journal(tmp_path/'journal.sqlite3')
    worker = Worker(SimpleNamespace(state_dir=tmp_path), Mock(), journal=journal)
    def uncertain(args, before_mutation, **kwargs):
        before_mutation(0)
        raise AttentionRequired('Unknown send result')
    try:
        with patch('companion.whatsapp.send_current', side_effect=uncertain) as sender:
            assert worker.execute(job)['status'] == 'needs_attention'
            assert journal.state(job['id'])[1]
            assert worker.execute(job)['status'] == 'needs_attention'
            assert sender.call_count == 1
    finally:
        journal.close()


def test_contact_search_opens_only_unique_exact_sidebar_result():
    from companion.whatsapp import search_recipient
    search=TextBox('Search or start a new chat',130,120,230,18)
    contact=TextBox('MSV Krishna',150,230,110,18)
    value=adapter([search],[search],[contact],frame())
    with patch('companion.whatsapp.time.sleep'):
        search_recipient(value,'MSV Krishna')
    value.keys.assert_called_once_with('MSV Krishna')
    assert value.click.call_count==2


def test_already_selected_exact_chat_needs_no_search_typing():
    from companion.whatsapp import search_recipient
    value=adapter(frame())
    search_recipient(value,'MSV Krishna')
    value.keys.assert_not_called()
    value.click.assert_not_called()


def test_repeat_text_needs_an_additional_outgoing_bubble():
    old=frame(sent=True)
    new=frame(sent=True)+[TextBox(MESSAGE+' 15:31',1100,940,750,20,'outgoing_green')]
    value=adapter(old,frame(),frame(MESSAGE),old,new)
    with patch('companion.whatsapp.time.sleep'):
        assert send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:value)['outgoing_verified']
    assert value.observe.call_count==5


def test_old_matching_bubble_alone_never_confirms_repeated_send():
    old=frame(sent=True)
    value=adapter(old,frame(),frame(MESSAGE),*[old for _ in range(5)])
    with patch('companion.whatsapp.time.sleep'),pytest.raises(AttentionRequired,match='uncertain'):
        send_current(ARGS,before_mutation=Mock(),adapter_factory=lambda _:value)
    assert value.keys.call_count==2


def test_duplicate_contact_search_never_clicks_result():
    from companion.whatsapp import search_recipient
    search=TextBox('Search or start a new chat',130,120,230,18)
    contacts=[TextBox('MSV Krishna',150,y,110,18) for y in (230,310)]
    value=adapter([search],[search],contacts)
    with patch('companion.whatsapp.time.sleep'),pytest.raises(AttentionRequired,match='Multiple'):
        search_recipient(value,'MSV Krishna')
    assert value.click.call_count==1


def test_focused_caret_uses_independent_exact_full_window_search_text():
    from companion.whatsapp import search_recipient
    original=TextBox('Search or start a new chat',141,126,180,18)
    focused=[TextBox('bearch or start a new chat',141,124,180,18),
             TextBox('Q Search or start a new chat',111,124,210,18)]
    contact=TextBox('MSV Krishna',150,230,110,18)
    value=adapter([original],focused,[contact],frame())
    with patch('companion.whatsapp.time.sleep'):
        search_recipient(value,'MSV Krishna')
    value.keys.assert_called_once_with('MSV Krishna')


def test_unrecognized_search_text_never_types_a_recipient():
    from companion.whatsapp import search_recipient
    original=TextBox('Search or start a new chat',141,126,180,18)
    wrong=[TextBox('Other content',141,124,180,18)]
    value=adapter([original],wrong,wrong,wrong,wrong)
    with patch('companion.whatsapp.time.sleep'),pytest.raises(AttentionRequired,match='Nothing was entered'):
        search_recipient(value,'MSV Krishna')
    value.keys.assert_not_called()


def test_shared_group_mentions_are_not_recipient_matches():
    from companion.whatsapp import search_recipient
    search=TextBox('Search or start a new chat',141,126,180,18)
    matches=[TextBox('MSV Krishna',150,230,110,18),
             TextBox('Groups in common',85,340,140,18),
             TextBox('MSV Krishna',150,410,110,18)]
    value=adapter([search],[search],matches,frame())
    with patch('companion.whatsapp.time.sleep'):
        search_recipient(value,'MSV Krishna')
    assert value.click.call_count==2


def test_partial_or_message_body_match_cannot_be_a_contact():
    from companion.whatsapp import search_recipient
    search=TextBox('Search or start a new chat',130,120,230,18)
    wrong=[TextBox('MSV Krishna Jr',150,230,110,18),TextBox('MSV Krishna',900,300,110,18)]
    value=adapter([search],[search],wrong,wrong,wrong,wrong)
    with patch('companion.whatsapp.time.sleep'),pytest.raises(AttentionRequired,match='No unique'):
        search_recipient(value,'MSV Krishna')
    assert value.click.call_count==1
