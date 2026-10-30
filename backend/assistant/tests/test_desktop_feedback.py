from unittest.mock import patch
from assistant import models as m,commands,services
from assistant.desktop_feedback import feedback
from assistant.tasks import execute_run,deliver_command


def test_progress_and_terminal_feedback_are_ordered_and_deduplicated(user):
    command,_=commands.submit(user,'WhatsApp request',channel='telegram',external_key='123')
    with patch('assistant.services.kick'):
        result=services.queue_whatsapp_message(user,{'recipient':'Person','message':'Hello'})
    m.ActionExecution.objects.create(user=user,command=command,step=0,tool='send_whatsapp_message',
                                     args={},status='committed',result=result)
    execute_run(result['run_id'])
    job=m.DesktopJob.objects.get(run_id=result['run_id'])
    feedback(job,'opening');feedback(job,'opening');feedback(job,'searching')
    job.status='needs_attention';job.error='Exact recipient not found.'
    feedback(job,'needs_attention',job.error);feedback(job,'needs_attention',job.error)
    rows=list(command.deliveries.order_by('position'))
    assert len(rows)==3
    assert [r.position for r in rows]==[1002,1003,1004]
    assert 'Opening' in rows[0].text and 'Searching' in rows[1].text
    assert 'not confirmed' in rows[2].text and 'recipient not found' in rows[2].text
    command.refresh_from_db()
    assert command.response['desktop_stage']=='needs_attention'


def test_success_feedback_distinguishes_outgoing_from_delivery(user):
    command,_=commands.submit(user,'WhatsApp request')
    with patch('assistant.services.kick'):
        result=services.queue_whatsapp_message(user,{'recipient':'Person','message':'Hello'})
    m.ActionExecution.objects.create(user=user,command=command,step=0,tool='send_whatsapp_message',args={},result=result)
    execute_run(result['run_id'])
    job=m.DesktopJob.objects.get(run_id=result['run_id']);job.result={'outgoing_verified':True}
    feedback(job,'completed')
    command.refresh_from_db()
    assert 'outgoing message verified' in command.response['reply_text']
    assert 'Delivery/read status is not verified' in command.response['reply_text']


def test_status_notice_survives_uncertain_ack_without_replaying_it(user,settings):
    settings.TELEGRAM_BOT_TOKEN='123:fixture';settings.TELEGRAM_CHAT_ID='123'
    command,_=commands.submit(user,'WhatsApp request')
    m.ActionExecution.objects.create(user=user,command=command,step=0,tool='send_whatsapp_message',args={},result={})
    uncertain=m.Delivery.objects.create(user=user,command=command,position=1001,destination='123',text='Queued',status='needs_attention')
    status=m.Delivery.objects.create(user=user,command=command,position=1002,destination='123',text='Desktop stopped: focus refused.')
    with patch('assistant.integrations.telegram.send_message',return_value=[{'message_id':50}]) as send:
        deliver_command(str(status.id))
    send.assert_called_once()
    assert send.call_args.args[2]=='Desktop stopped: focus refused.'
    uncertain.refresh_from_db();status.refresh_from_db()
    assert uncertain.status=='needs_attention' and status.status=='sent'


def test_uncertain_after_send_does_not_claim_message_was_not_sent(user):
    command,_=commands.submit(user,'WhatsApp request',channel='telegram',external_key='123')
    with patch('assistant.services.kick'):
        result=services.queue_whatsapp_message(user,{'recipient':'Person','message':'Hello'})
    m.ActionExecution.objects.create(user=user,command=command,step=0,tool='send_whatsapp_message',args={},result=result)
    execute_run(result['run_id'])
    job=m.DesktopJob.objects.get(run_id=result['run_id'])
    feedback(job,'checking')
    feedback(job,'needs_attention','Uncertain receipt')
    command.refresh_from_db()
    assert 'may already be sent' in command.response['reply_text']
    assert 'will not resend automatically' in command.response['reply_text']
    assert 'may already be sent' in command.deliveries.order_by('-position').first().text
