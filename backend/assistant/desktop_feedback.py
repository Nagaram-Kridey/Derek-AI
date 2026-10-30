"""Owner-scoped, deduplicated feedback for one-off chat desktop actions."""
from django.db import transaction
from . import models as m

STAGES={
    'opening':'Opening WhatsApp on your laptop…',
    'searching':'Searching WhatsApp for the exact recipient…',
    'recipient':'Recipient verified. Checking the composer…',
    'verifying':'Draft entered. Verifying the exact text before sending…',
    'checking':'Send input issued. Checking for the outgoing message…',
}


def feedback(job, stage, error=''):
    if stage not in {*STAGES,'completed','failed','needs_attention','needs_approval'}:
        return
    with transaction.atomic():
        action=(m.ActionExecution.objects.filter(user_id=job.user_id,tool='send_whatsapp_message',
                 result__run_id=str(job.run_id)).select_related('command').first())
        if not action:
            return
        command=m.Command.objects.select_for_update().get(pk=action.command_id)
        detail={'run_id':str(job.run_id),'stage':stage}
        if m.CommandEvent.objects.filter(command=command,kind='desktop_progress',detail=detail).exists():
            return
        m.CommandEvent.objects.create(command=command,kind='desktop_progress',detail=detail)
        if stage=='completed':
            text=('WhatsApp: outgoing message verified. Delivery/read status is not verified.'
                  if job.result.get('outgoing_verified') else 'WhatsApp task finished. Inspect Activity for its saved result.')
        elif stage in {'failed','needs_attention','needs_approval'}:
            issued = m.CommandEvent.objects.filter(command=command, kind='desktop_progress',
                detail={'run_id': str(job.run_id), 'stage': 'checking'}).exists()
            if issued:
                text = ('WhatsApp: send was attempted, but Derek could not verify the outgoing bubble. '
                        'The message may already be sent. Check WhatsApp before retrying; Derek will not resend automatically.')
            else:
                text='WhatsApp stopped; sending was not confirmed. '+(error[:700] or 'Inspect the desktop and Activity before retrying.')
        else:
            text=STAGES[stage]
        m.Message.objects.create(conversation=command.conversation,role='assistant',content=text,
                                 metadata={'desktop_run_id':str(job.run_id),'desktop_stage':stage})
        command.response={**command.response,'desktop_stage':stage,'desktop_run_id':str(job.run_id),'reply_text':text}
        command.save(update_fields=['response'])
        if command.channel=='telegram':
            session=m.ChannelSession.objects.filter(user_id=job.user_id,channel='telegram',
                                                    conversation_id=command.conversation_id).first()
            if session:
                last=command.deliveries.order_by('-position').first()
                m.Delivery.objects.create(user_id=job.user_id,command=command,
                    position=max(1002,last.position+1 if last else 1002),destination=session.external_key,text=text)
