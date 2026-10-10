import logging
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from celery import shared_task
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from . import models as m
from .contracts import DESKTOP_TOOLS
from .services import state, run_allowed, calendar_token, start_run
from .scheduling import next_due
from .utils import audit, kick, BudgetGateway

logger = logging.getLogger(__name__)

def notify(user, text):
    notification = m.Notification.objects.create(user=user, text=text[:12000])
    kick(deliver_notification, str(notification.id))
    return notification

@shared_task(name="assistant.deliver_notification")
def deliver_notification(notification_id):
    with transaction.atomic():
        row = m.Notification.objects.select_for_update().get(pk=notification_id)
        if row.status != "pending":
            return
        row.status = "sending"
        row.started_at = timezone.now()
        row.save()
    try:
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            from .integrations.telegram import send_message
            send_message(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, row.text)
            row.status, row.sent_at = "sent", timezone.now()
        else:
            row.status = "in_app"
    except Exception:
        # Network timeouts may follow successful delivery. Never resend blindly.
        row.status, row.error = "needs_attention", "Delivery could not be confirmed. Check Telegram before retrying."
    row.save()
    audit(row.user, "notification.delivery", notification_id=str(row.id), status=row.status)

def build_report(row):
    from .integrations.research import run_research
    from .integrations.docs import generate_report
    content = run_research(row.content.get("topic", row.title), BudgetGateway(row.user), include_academic=row.content.get("include_academic", False))
    with TemporaryDirectory(prefix="derek-report-") as folder:
        paths = generate_report(content, folder)
        for extension in ("docx", "pdf"):
            with Path(paths[extension]).open("rb") as source:
                getattr(row, extension).save(f"{row.id}.{extension}", File(source), save=False)
    row.content, row.citations, row.status = content, content["citations"], "completed"
    row.save()
    return {"report_id": str(row.id), "title": row.title, "status": row.status}

@shared_task(name="assistant.research_report", soft_time_limit=1140, time_limit=1200)
def research_report(report_id):
    with transaction.atomic():
        row = m.Report.objects.select_for_update().get(pk=report_id)
        if row.status != "queued" or state(row.user).paused:
            return
        row.status = "running"
        row.save()
    try:
        result = build_report(row)
        notify(row.user, f"Research report ready: {row.title}. Download it from Reports.")
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            from .integrations.telegram import send_document
            with TemporaryDirectory() as folder:
                path = Path(folder) / f"{row.id}.pdf"
                with row.pdf.open("rb") as source:
                    path.write_bytes(source.read())
                try:
                    send_document(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, path)
                except Exception:
                    audit(row.user, "report.telegram_failed", report_id=str(row.id))
        return result
    except Exception as exc:
        from .integrations.errors import ConfigError, ProviderError
        row.status = "failed"
        row.error = str(exc) if isinstance(exc, (ValueError, ConfigError, ProviderError)) else "Research failed. Check worker logs and provider configuration."
        row.save()
        audit(row.user, "report.failed", report_id=str(row.id))

@shared_task(name="assistant.execute_run", soft_time_limit=1140, time_limit=1200)
def execute_run(run_id):
    with transaction.atomic():
        run = m.WorkflowRun.objects.select_for_update(of=("self",)).select_related("user", "workflow").get(pk=run_id)
        if run.status != "queued" or not run_allowed(run):
            return
        if run.step_index >= len(run.snapshot["steps"]):
            run.status = "completed"
            run.save()
            return
        step = run.snapshot["steps"][run.step_index]
        if step["tool"] in DESKTOP_TOOLS:
            m.DesktopJob.objects.get_or_create(run=run, step_index=run.step_index, defaults={"user": run.user, "tool": step["tool"], "args": step["args"], "policy": {"allowed_paths": run.snapshot["allowed_paths"], "allowed_domains": run.snapshot["allowed_domains"]}})
            run.status = "waiting_desktop"
            run.save()
            return
        run.status, run.execution_started_at = "running", timezone.now()
        run.save()
    try:
        if step["tool"] == "notify":
            result = {"notification_id": str(notify(run.user, step["args"]["message"]).id)}
        elif step["tool"] == "research.run":
            row = m.Report.objects.create(user=run.user, title=step["args"]["topic"][:240], status="running", content={"include_academic": step["args"].get("include_academic", False), "topic": step["args"]["topic"]})
            result = build_report(row)
            notify(run.user, f"Research report ready: {row.title}.")
        elif step["tool"] == "calendar.create":
            from .integrations.calendar import create_event
            result = create_event(calendar_token(run.user), step["args"])
        elif step["tool"] == "calendar.update":
            from .integrations.calendar import update_event
            args = step["args"].copy()
            event_id = args.pop("event_id")
            result = update_event(calendar_token(run.user), event_id, args)
        else:
            raise ValueError("Unsupported cloud action")
        with transaction.atomic():
            run = m.WorkflowRun.objects.select_for_update().get(pk=run.pk)
            if run.status == "cancelled":
                audit(run.user, "run.cancelled_action_finished", run_id=str(run.id), step=run.step_index)
                return
            run.results.append({"tool": step["tool"], "result": result})
            run.step_index += 1
            run.status = "completed" if run.step_index >= len(run.snapshot["steps"]) else "queued"
            run.execution_started_at = None
            run.save()
        audit(run.user, "run.step_completed", run_id=str(run.id), tool=step["tool"])
        if run.status == "queued":
            kick(execute_run, str(run.id))
    except Exception:
        # A request may have committed remotely before timing out.
        m.WorkflowRun.objects.filter(pk=run.pk).exclude(status="cancelled").update(status="needs_attention", error="Action outcome is uncertain. Inspect the external service before starting another run.")
        audit(run.user, "run.needs_attention", run_id=str(run.id), tool=step["tool"])

@shared_task(name="assistant.execute_occurrence")
def execute_occurrence(occurrence_id):
    with transaction.atomic():
        row = m.ScheduledOccurrence.objects.select_for_update().select_related("task__user").get(pk=occurrence_id)
        if row.status != "pending" or state(row.task.user).paused:
            return
        row.status = "running"
        row.started_at = timezone.now()
        row.save()
    task = row.task
    try:
        if task.kind == "reminder":
            row.result = {"notification_id": str(notify(task.user, task.payload["message"]).id)}
        elif task.kind == "research":
            report = m.Report.objects.create(user=task.user, title=task.payload["topic"][:240], content={"topic": task.payload["topic"]})
            kick(research_report, str(report.id))
            row.result = {"report_id": str(report.id)}
        elif task.kind == "workflow":
            workflow = m.Workflow.objects.get(pk=task.payload["workflow_id"], user=task.user)
            row.result = {"run_id": str(start_run(workflow).id)}
        row.status = "completed"
    except Exception:
        row.status, row.error = "needs_attention", "Scheduled execution failed; inspect its status before retrying."
    row.save()
    audit(task.user, "schedule.dispatched", task_id=str(task.id), occurrence_id=str(row.id), status=row.status)

@shared_task(name="assistant.tick")
def tick():
    now = timezone.now()
    m.AssistantState.objects.all().update(scheduler_heartbeat_at=now)
    # DB outbox rows survive broker outages. Concurrent workers claim rows under locks.
    for pk in m.ScheduledTask.objects.filter(enabled=True, next_run_at__lte=now).values_list("pk", flat=True)[:100]:
        with transaction.atomic():
            task = m.ScheduledTask.objects.select_for_update().get(pk=pk)
            if not task.enabled or not task.next_run_at or task.next_run_at > now or state(task.user).paused:
                continue
            m.ScheduledOccurrence.objects.get_or_create(task=task, scheduled_for=task.next_run_at)
            task.next_run_at = next_due(task.schedule, now)
            if task.next_run_at is None:
                task.enabled = False
            task.save()
    for row in m.ScheduledOccurrence.objects.filter(status="pending").select_related("task__user")[:100]:
        if not state(row.task.user).paused:
            kick(execute_occurrence, str(row.id))
    for row in m.WorkflowRun.objects.filter(status="queued").select_related("user", "workflow")[:100]:
        if run_allowed(row):
            kick(execute_run, str(row.id))
    for row in m.Report.objects.filter(status="queued").select_related("user")[:100]:
        if not state(row.user).paused:
            kick(research_report, str(row.id))
    for row in m.Notification.objects.filter(status="pending")[:100]:
        kick(deliver_notification, str(row.id))
    for row in m.TelegramUpdate.objects.filter(status="pending")[:100]:
        kick(process_telegram, row.update_id)
    # Never automatically replay uncertain desktop or remote mutations.
    expired = m.DesktopJob.objects.filter(status="leased", lease_expires_at__lt=now)
    for job in expired:
        with transaction.atomic():
            changed = m.DesktopJob.objects.filter(pk=job.pk, status="leased", lease_expires_at__lt=now).update(status="needs_attention", error="Desktop lease expired; inspect the local journal before rerunning.")
            if changed:
                m.WorkflowRun.objects.filter(pk=job.run_id).exclude(status="cancelled").update(status="needs_attention", error="Desktop action outcome is uncertain.")
    m.WorkflowRun.objects.filter(status="running", execution_started_at__lt=now - timedelta(minutes=25)).update(status="needs_attention", error="Worker stopped during execution; inspect the action before rerunning.")
    m.Report.objects.filter(status="running", updated_at__lt=now - timedelta(minutes=25)).update(status="failed", error="Research worker interrupted; start a new report.")
    m.Approval.objects.filter(status="pending", expires_at__lt=now).update(status="expired")
    m.WorkflowRun.objects.filter(status="needs_approval", approvals__status="expired").update(status="needs_attention", error="Sensitive-action approval expired. Inspect and cancel this run before starting another.")
    m.Notification.objects.filter(status="sending", started_at__lt=now-timedelta(minutes=5)).update(status="needs_attention", error="Delivery worker stopped; check Telegram before retrying.")
    m.ScheduledOccurrence.objects.filter(status="running", started_at__lt=now-timedelta(minutes=10)).update(status="needs_attention", error="Schedule worker stopped; inspect created jobs before retrying.")
    m.TelegramUpdate.objects.filter(status="running", started_at__lt=now-timedelta(minutes=10)).update(status="needs_attention", payload={})

@shared_task(name="assistant.process_telegram", soft_time_limit=240, time_limit=300)
def process_telegram(update_id):
    from django.contrib.auth import get_user_model
    from .services import turn
    from .integrations.telegram import send_message, download_voice
    from .integrations.voice import transcribe_audio
    with transaction.atomic():
        row = m.TelegramUpdate.objects.select_for_update().get(pk=update_id)
        if row.status != "pending":
            return
        row.status = "running"
        row.started_at = timezone.now()
        row.save()
    try:
        user = get_user_model().objects.get(is_active=True)
        message = row.payload["message"]
        text = message.get("text", "")
        if "voice" in message:
            data = download_voice(settings.TELEGRAM_BOT_TOKEN, message["voice"]["file_id"])
            with TemporaryDirectory() as folder:
                path = Path(folder) / "voice.ogg"
                path.write_bytes(data)
                text = transcribe_audio(path, settings.WHISPER_MODEL)
        result = turn(user, text)
        send_message(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, result["reply_text"])
        row.status = "completed"
    except Exception:
        row.status = "needs_attention"
        logger.warning("Telegram update failed; inspect provider configuration. update_id=%s", update_id)
    row.payload = {}
    row.save()
