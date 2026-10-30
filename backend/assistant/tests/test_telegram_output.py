from unittest.mock import patch
from assistant import commands, models as m


def test_saved_output_is_complete_idempotent_and_never_reruns(client, user, settings):
    settings.TELEGRAM_BOT_TOKEN='123:test'
    settings.TELEGRAM_CHAT_ID='456'
    command,_=commands.submit(user,'Explain caching')
    text='\n\n'.join(f'Point {i}. '+('Useful explanation. '*45) for i in range(12))
    command.status='completed'
    command.response=commands.response_for(command,text)
    command.save()
    with patch('assistant.command_views.kick'),patch('assistant.commands.run') as run:
        first=client.post(f'/v1/commands/{command.id}/telegram/',{},format='json')
        second=client.post(f'/v1/commands/{command.id}/telegram/',{},format='json')
    assert first.status_code == second.status_code == 200
    assert first.data['deliveries']==second.data['deliveries']
    blocks=list(command.deliveries.order_by('position').values_list('text',flat=True))
    assert len(blocks)>10 and all(len(b)<=500 for b in blocks)
    assert ' '.join(' '.join(blocks).split())==' '.join(text.split())
    assert set(command.deliveries.values_list('destination',flat=True))=={'456'}
    run.assert_not_called()


def test_output_rejects_pending_commands_and_other_owner(client,user,settings):
    settings.TELEGRAM_BOT_TOKEN='123:test';settings.TELEGRAM_CHAT_ID='456'
    command,_=commands.submit(user,'pending')
    assert client.post(f'/v1/commands/{command.id}/telegram/',{},format='json').status_code==409
    from django.contrib.auth import get_user_model
    other=get_user_model().objects.create_user('other')
    m.Command.objects.filter(pk=command.pk).update(user=other)
    assert client.post(f'/v1/commands/{command.id}/telegram/',{},format='json').status_code==404
    assert not command.deliveries.exists()
