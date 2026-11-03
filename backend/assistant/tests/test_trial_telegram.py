from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from assistant import trial_telegram as tg
from assistant.models import Command, Conversation
from assistant.telegram_link_models import (
    TelegramLink,
    TelegramLinkGrant,
    TrialTelegramReceipt,
)
from assistant.utils import digest

pytestmark = pytest.mark.django_db

@pytest.fixture
def trial(settings):
    settings.TEST_WORKSPACE=True
    settings.TEST_OPEN_SIGNUP=True
    settings.TEST_TELEGRAM_BOT_TOKEN='123:fake'
    settings.TEST_TELEGRAM_BOT_USERNAME='derek_test_bot'

def update(code, identifier=1, chat=123, kind='private'):
    return {'update_id':identifier,'message':{'text':'/start '+code,'chat':{'id':chat,'type':kind},'from':{'id':chat,'username':'tester'}}}

def grant(user, code='secret', expired=False):
    return TelegramLinkGrant.objects.create(user=user,digest=digest(code),expires_at=timezone.now()+timedelta(seconds=-1 if expired else 300))

def test_link_private_one_use_and_disconnect(client,user,trial):
    result=client.post('/v1/telegram/link/',{},format='json')
    assert result.status_code==200
    code=result.data['url'].split('start=')[1]
    tg.handle_update(update(code))
    assert TelegramLink.objects.get(user=user).chat_id=='123'
    tg.handle_update(update(code,2,456))
    assert TelegramLink.objects.get(user=user).chat_id=='123'
    assert client.get('/v1/telegram/link/').data['connected']
    assert client.delete('/v1/telegram/link/').status_code==200
    assert not TelegramLink.objects.exists()

def test_expired_group_and_chat_theft(user,trial):
    grant(user,expired=True)
    tg.handle_update(update('secret'))
    assert not TelegramLink.objects.exists()
    TelegramLinkGrant.objects.all().delete();grant(user,'fresh')
    tg.handle_update(update('fresh',2,kind='group'))
    assert not TelegramLink.objects.exists()
    tg.handle_update(update('fresh',3))
    other=get_user_model().objects.create_user('other',is_staff=True)
    grant(other,'other')
    tg.handle_update(update('other',4))
    assert TelegramLink.objects.get(chat_id='123').user_id==user.pk

def test_bound_inbound_duplicate_and_no_replay_after_send_error(user,trial):
    TelegramLink.objects.create(user=user,chat_id='123',telegram_user_id='123')
    data=update('ignored');data['message']['text']='Hello'
    tg.handle_update(data);tg.handle_update(data)
    assert Command.objects.filter(user=user).count()==1
    command=Command.objects.get(user=user)
    command.status='completed';command.response={'reply_text':'answer'};command.save()
    with patch.object(tg,'_call',side_effect=lambda token,method,**kw: {} if method=='getWebhookInfo' else []), patch.object(tg,'send_message',side_effect=ValueError('uncertain')) as send:
        tg.poll_once();tg.poll_once()
        assert send.call_count==1
    assert TrialTelegramReceipt.objects.get().status=='needs_attention'

def test_send_uses_owned_chat_only(client,user,trial):
    other=get_user_model().objects.create_user('other')
    conv=Conversation.objects.create(user=other,title='private')
    command=Command.objects.create(user=other,conversation=conv,request_id='x',input_text='x',fingerprint='x',status='completed',response={'reply_text':'private'})
    with patch.object(tg,'send_message') as send:
        assert client.post('/v1/telegram/send/',{'command_id':str(command.pk)},format='json').status_code==404
        send.assert_not_called()
