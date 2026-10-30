from datetime import timedelta
from django.utils import timezone
from assistant import commands, models as m
from assistant.delivery_queue import next_delivery
from assistant.tasks import deliver_command
from unittest.mock import patch


def bubble(user,command,position,**options):
    return m.Delivery.objects.create(user=user,command=command,position=position,destination='123',text='Response',**options)


def test_future_prior_bubble_does_not_starve_new_command(user):
    old,_=commands.submit(user,'old',request_id='old')
    current,_=commands.submit(user,'current',request_id='current')
    bubble(user,old,0,due_at=timezone.now()+timedelta(hours=1))
    bubble(user,old,1,due_at=timezone.now()-timedelta(minutes=1))
    expected=bubble(user,current,0)
    assert next_delivery().pk==expected.pk


def test_sequence_and_uncertain_destination_are_preserved(user):
    command,_=commands.submit(user,'message')
    first=bubble(user,command,0)
    bubble(user,command,1,due_at=timezone.now()-timedelta(minutes=1))
    assert next_delivery().pk==first.pk
    first.status='sending';first.save()
    assert next_delivery() is None


def test_stale_backlog_is_not_silently_sent(user):
    command,_=commands.submit(user,'old')
    row=bubble(user,command,0)
    m.Delivery.objects.filter(pk=row.pk).update(created_at=timezone.now()-timedelta(days=2))
    with patch('assistant.integrations.telegram.send_message') as send:
        deliver_command(str(row.pk))
    send.assert_not_called()
    row.refresh_from_db()
    assert row.status=='needs_attention'
