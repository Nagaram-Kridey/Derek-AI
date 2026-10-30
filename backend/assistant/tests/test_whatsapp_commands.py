from unittest.mock import patch
from assistant import commands, models as m, services
from assistant.tasks import process_command, execute_run


def test_chat_request_requires_confirmation_and_queues_only_once(user, client):
    command,_=commands.submit(user,'Send a WhatsApp message to MSV Krishna saying: Hello')
    with patch('assistant.services.kick'),patch('assistant.commands.kick'):
        process_command(str(command.pk))
        proposal=m.ActionProposal.objects.get(action__command=command)
        assert 'MSV Krishna: Hello' in proposal.readback
        assert not m.DesktopJob.objects.exists()
        assert not m.WorkflowRun.objects.exists()
        result=commands.decide(proposal,True,proposal.revision,proposal.payload_digest)
        assert result['status']=='queued'
        run=m.WorkflowRun.objects.get(pk=result['run_id'])
        assert run.snapshot['steps'][0]['args']['open_and_search']
        assert run.snapshot['steps'][0]['args']['transport']=='brave_web'
        assert 'Brave WhatsApp Web' in proposal.readback
        commands.decide(proposal,True,proposal.revision,proposal.payload_digest)
        assert m.WorkflowRun.objects.count()==1
        execute_run(str(run.id))
    job=m.DesktopJob.objects.get(run=run)
    assert job.tool=='desktop.whatsapp'
    assert job.args['message']=='Hello'
    assert job.policy['allowed_tools']==['desktop.whatsapp']
    assert client.get('/v1/workflows/').data==[]


def test_cancelled_chat_message_creates_no_desktop_run(user):
    command,_=commands.submit(user,'Send a WhatsApp message to MSV Krishna saying: Hello')
    process_command(str(command.pk))
    proposal=m.ActionProposal.objects.get(action__command=command)
    commands.decide(proposal,False,proposal.revision,proposal.payload_digest)
    assert not m.WorkflowRun.objects.exists()


def test_one_off_message_cannot_be_manually_replayed(user):
    from pytest import raises
    with patch('assistant.services.kick'):
        result=services.queue_whatsapp_message(user,{'recipient':'Person','message':'Hello','open_and_search':True})
    run=m.WorkflowRun.objects.get(pk=result['run_id'])
    with raises(ValueError,match='cannot be replayed'):
        services.start_run(run.workflow)
