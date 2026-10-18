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

def build_report(row, workflow_run_id=None):
    from .integrations.research import run_research
    from .integrations.docs import generate_report
    from .integrations.errors import RequestCancelled
    def cancelled():
        from django.db import connection
        try:
            return (not m.Report.objects.filter(pk=row.pk, status="running").exists()
                    or (workflow_run_id is not None and not m.WorkflowRun.objects.filter(pk=workflow_run_id, status="running").exists()))
        finally:
            if not connection.in_atomic_block:
                connection.close()
    def progress(stage, label, **detail):
        if cancelled():
            raise RequestCancelled("Research cancelled.")
        updated = m.Report.objects.filter(pk=row.pk, status="running").update(progress={"stage": stage, "label": label, **detail, "updated_at": timezone.now().isoformat()}, updated_at=timezone.now())
        if not updated:
            raise RequestCancelled("Research cancelled.")
    if cancelled():
        raise RequestCancelled("Research cancelled before provider setup.")
    gateway = BudgetGateway(row.user, cancelled=cancelled)
    topic = row.content.get("topic", row.title)
    if row.content.get("report_kind") == "project_ideas":
        topic = f"{topic[:1800]} Research as of {timezone.localdate().isoformat()}; use current primary sources and distinguish documented capabilities from speculative opportunities."
    content = run_research(topic, gateway, include_academic=row.content.get("include_academic", False), progress=progress)
    if row.content.get("report_kind") == "project_ideas":
        progress("project_ideas", "Designing five proposals and selecting two")
        from .integrations.project_ideas import add_project_ideas
        recent = []
        for prior in m.Report.objects.filter(user=row.user, status="completed", created_at__gte=timezone.now()-timedelta(days=7)).exclude(pk=row.pk).order_by("-created_at")[:14]:
            recent.extend(idea["title"] for idea in prior.content.get("project_ideas", []) if isinstance(idea, dict) and "title" in idea)
        content = add_project_ideas(content, gateway, recent)
        content["title"] = f"Enterprise software and AI project ideas - {timezone.localdate().isoformat()}"
        row.title = content["title"]
    progress("exporting", "Preparing PDF and Word files")
    with TemporaryDirectory(prefix="derek-report-") as folder:
        paths = generate_report(content, folder)
        for extension in ("docx", "pdf"):
            with Path(paths[extension]).open("rb") as source:
                getattr(row, extension).save(f"{row.id}.{extension}", File(source), save=False)
    with transaction.atomic():
        run = m.WorkflowRun.objects.select_for_update().filter(pk=workflow_run_id).first() if workflow_run_id else None
        current = m.Report.objects.select_for_update().filter(pk=row.pk).first()
        if not current or current.status != "running" or (workflow_run_id and (not run or run.status != "running")):
            row.docx.delete(save=False)
            row.pdf.delete(save=False)
            raise RequestCancelled("Research cancelled before publication.")
        row.content, row.citations, row.status = content, content["citations"], "completed"
        row.progress = {"stage": "completed", "label": "Report ready", "updated_at": timezone.now().isoformat(),
                        "telegram_delivery": {"status": "pending" if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID else "not_configured", "due_at": timezone.now().isoformat()}}
        row.save()
    return {"report_id": str(row.id), "title": row.title, "status": row.status}

def deliver_report_file(row):
    # The completion transaction created this durable file-delivery intent.
    # Research does not wait on Telegram and is never repeated for delivery.
    if row.progress.get("telegram_delivery", {}).get("status") == "pending":
        kick(send_report_file, str(row.id))


@shared_task(name="assistant.send_report_file")
def send_report_file(report_id):
    from datetime import datetime
    from .integrations.telegram import send_document, TelegramRateLimit
    with transaction.atomic():
        row = m.Report.objects.select_for_update().filter(pk=report_id, status="completed").first()
        if not row:
            return
        delivery = row.progress.get("telegram_delivery", {})
        if delivery.get("status") != "pending":
            return
        if delivery.get("due_at") and datetime.fromisoformat(delivery["due_at"]) > timezone.now():
            return
        delivery = {**delivery, "status": "sending", "started_at": timezone.now().isoformat()}
        row.progress = {**row.progress, "telegram_delivery": delivery}
        row.save(update_fields=["progress"])
    try:
        with TemporaryDirectory() as folder:
            path = Path(folder) / f"{row.id}.pdf"
            with row.pdf.open("rb") as source:
                path.write_bytes(source.read())
            result = send_document(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, path)
        delivery.update(status="sent", sent_at=timezone.now().isoformat(), message_id=str(result["message_id"]), error="")
    except TelegramRateLimit as exc:
        delivery.update(status="pending", due_at=(timezone.now()+timedelta(seconds=exc.retry_after)).isoformat())
    except Exception:
        # Unknown send outcomes are not safe to repeat automatically.
        delivery.update(status="needs_attention", error="PDF delivery could not be confirmed. Check Telegram before requesting another copy.")
    with transaction.atomic():
        current = m.Report.objects.select_for_update().filter(pk=row.pk).first()
        if current:
            current.progress = {**current.progress, "telegram_delivery": delivery}
            current.save(update_fields=["progress"])
    audit(row.user, "report.telegram_" + delivery["status"], report_id=str(row.id))

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
        deliver_report_file(row)
        return result
    except Exception as exc:
        from .integrations.errors import ConfigError, ProviderError, RequestCancelled
        if isinstance(exc, RequestCancelled):
            return {"report_id": str(row.id), "status": "cancelled"}
        row.status = "failed"
        row.error = str(exc) if isinstance(exc, (ValueError, ConfigError, ProviderError)) else "Research failed. Check worker logs and provider configuration."
        m.Report.objects.filter(pk=row.pk, status="running").update(status="failed", error=row.error, updated_at=timezone.now())
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
            row = m.Report.objects.create(user=run.user, title=step["args"]["topic"][:240], status="running", content={"include_academic": step["args"].get("include_academic", False), "topic": step["args"]["topic"], "report_kind": step["args"].get("report_kind", "standard")})
            try:
                result = build_report(row, workflow_run_id=run.pk)
            except Exception as exc:
                from .integrations.errors import ConfigError, ProviderError, RequestCancelled
                if isinstance(exc, RequestCancelled):
                    m.Report.objects.filter(pk=row.pk, status="running").update(status="cancelled", progress={"stage": "cancelled", "label": "Workflow research stopped"}, updated_at=timezone.now())
                    m.WorkflowRun.objects.filter(pk=run.pk).update(status="cancelled", error="Research was stopped before the remaining workflow steps.")
                    return
                row.status = "failed"
                row.error = str(exc) if isinstance(exc, (ValueError, ConfigError, ProviderError)) else "Research failed. Check worker logs and provider configuration."
                m.Report.objects.filter(pk=row.pk, status="running").update(status="failed", error=row.error, updated_at=timezone.now())
                audit(row.user, "report.failed", report_id=str(row.id))
                raise
            notify(run.user, f"Research report ready: {row.title}. PDF and DOCX are available in Reports.")
            deliver_report_file(row)
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
    except Exception as exc:
        # A request may have committed remotely before timing out.
        from .integrations.errors import ConfigError, ProviderError
        read_only_failure = step["tool"] == "research.run" and isinstance(exc, (ConfigError, ProviderError, ValueError))
        status = "failed" if read_only_failure else "needs_attention"
        message = "Research could not finish: " + str(exc)[:1000] if read_only_failure else "Action outcome is uncertain. Inspect the external service before starting another run."
        m.WorkflowRun.objects.filter(pk=run.pk).exclude(status="cancelled").update(status=status, error=message)
        audit(run.user, "run." + status, run_id=str(run.id), tool=step["tool"])

@shared_task(name="assistant.execute_occurrence")
def execute_occurrence(occurrence_id):
    task_id = m.ScheduledOccurrence.objects.filter(pk=occurrence_id).values_list("task_id", flat=True).first()
    if not task_id:
        return
    with transaction.atomic():
        if not m.ScheduledTask.objects.select_for_update().filter(pk=task_id).first():
            return
        row = m.ScheduledOccurrence.objects.select_for_update(of=("self",)).select_related("task__user").filter(pk=occurrence_id).first()
        if not row:
            return
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
            report = m.Report.objects.create(user=task.user, title=task.payload["topic"][:240], content=task.payload)
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
    for pk in m.Report.objects.filter(status="completed", progress__telegram_delivery__status="pending").values_list("pk", flat=True)[:100]:
        kick(send_report_file, str(pk))
    for report in m.Report.objects.filter(status="completed", progress__telegram_delivery__status="sending")[:100]:
        started = report.progress.get("telegram_delivery", {}).get("started_at")
        from datetime import datetime
        if started and datetime.fromisoformat(started) < now-timedelta(minutes=5):
            with transaction.atomic():
                current = m.Report.objects.select_for_update().get(pk=report.pk)
                delivery = current.progress.get("telegram_delivery", {})
                if delivery.get("status") == "sending" and delivery.get("started_at") == started:
                    current.progress = {**current.progress, "telegram_delivery": {**delivery, "status": "needs_attention", "error": "Delivery worker stopped. Check Telegram before requesting another copy."}}
                    current.save(update_fields=["progress"])
    for row in m.Notification.objects.filter(status="pending")[:100]:
        kick(deliver_notification, str(row.id))
    for row in m.TelegramUpdate.objects.filter(status="pending")[:100]:
        kick(process_telegram, row.update_id)
    for pk in m.Command.objects.filter(status="queued").order_by("created_at").values_list("pk", flat=True)[:50]:
        kick(process_command, str(pk))
    for pk in m.Delivery.objects.filter(status="pending", due_at__lte=now).values_list("pk", flat=True)[:100]:
        kick(deliver_command, str(pk))
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
    from .commands import response_for, event
    for command in m.Command.objects.filter(status="running", started_at__lt=now-timedelta(minutes=25)):
        with transaction.atomic():
            command = m.Command.objects.select_for_update().get(pk=command.pk)
            if command.status != "running":
                continue
            command.status = "needs_attention"
            command.error = "The command worker stopped. Inspect saved actions before issuing a new command."
            command.response = response_for(command, command.error)
            command.finished_at = now
            command.save(update_fields=["status", "error", "response", "finished_at"])
            event(command, "needs_attention", response=command.response)
    from .commands import expire_proposals
    expire_proposals(now)
    m.CommandCancellation.objects.filter(created_at__lt=now-timedelta(days=1)).delete()
    m.FormRequest.objects.filter(created_at__lt=now-timedelta(days=30)).delete()
    m.ActionProposal.objects.filter(status="executing", decided_at__lt=now-timedelta(minutes=5)).update(status="needs_attention")
    m.Delivery.objects.filter(status="sending", started_at__lt=now-timedelta(minutes=5)).update(status="needs_attention", error="Delivery outcome is uncertain. Check Telegram before retrying.")

@shared_task(name="assistant.process_command", soft_time_limit=1140, time_limit=1200)
def process_command(command_id):
    from .commands import run
    try:
        command = run(command_id)
    except m.Command.DoesNotExist:
        return  # History may have been deleted after cancellation.
    if command and command.channel == "telegram":
        for pk in command.deliveries.filter(status="pending").values_list("pk", flat=True):
            kick(deliver_command, str(pk))


@shared_task(name="assistant.deliver_command")
def deliver_command(delivery_id):
    from .integrations.telegram import send_message, TelegramRateLimit
    with transaction.atomic():
        row = m.Delivery.objects.select_for_update().select_related("user").get(pk=delivery_id)
        if row.status != "pending" or row.due_at > timezone.now():
            return
        m.AssistantState.objects.select_for_update().get_or_create(user=row.user)
        previous = m.Delivery.objects.filter(command_id=row.command_id, position__lt=row.position).exclude(status="sent")
        if previous.filter(status="needs_attention").exists():
            row.status, row.error = "needs_attention", "An earlier message has an uncertain outcome. Check Telegram."
            row.save(update_fields=["status", "error"])
            return
        if previous.exists() or m.Delivery.objects.filter(destination=row.destination, status="sending").exists():
            return
        last = m.Delivery.objects.filter(destination=row.destination, status="sent").order_by("-sent_at").first()
        if last and last.sent_at > timezone.now() - timedelta(seconds=1.1):
            row.due_at = last.sent_at + timedelta(seconds=1.1)
            row.save(update_fields=["due_at"])
            if not settings.LOCAL_EXECUTION:
                transaction.on_commit(lambda: deliver_command.apply_async(args=[str(row.id)], countdown=2))
            return
        row.status, row.started_at = "sending", timezone.now()
        row.save(update_fields=["status", "started_at"])
    try:
        reply_markup = None
        if not m.Delivery.objects.filter(command_id=row.command_id, position__gt=row.position).exists():
            proposal = m.ActionProposal.objects.filter(action__command_id=row.command_id, status="pending", expires_at__gt=timezone.now()).first()
            if proposal:
                from .telegram_buttons import markup
                reply_markup = markup(proposal)
        results = send_message(settings.TELEGRAM_BOT_TOKEN, row.destination, row.text, reply_markup=reply_markup)
        row.provider_message_id = str(results[0]["message_id"])
        row.status, row.sent_at = "sent", timezone.now()
    except TelegramRateLimit as exc:
        row.status, row.due_at = "pending", timezone.now() + timedelta(seconds=exc.retry_after)
    except Exception:
        row.status, row.error = "needs_attention", "Delivery could not be confirmed. The command was not re-executed. Check Telegram."
    row.save()
    audit(row.user, "command.delivery", command_id=str(row.command_id), delivery_id=str(row.id), status=row.status)
    if row.status == "sent":
        next_row = m.Delivery.objects.filter(command_id=row.command_id, position__gt=row.position, status="pending").order_by("position").first()
        if next_row and not settings.LOCAL_EXECUTION:
            deliver_command.apply_async(args=[str(next_row.id)], countdown=2)


@shared_task(name="assistant.process_telegram", soft_time_limit=1140, time_limit=1200)
def process_telegram(update_id):
    from django.contrib.auth import get_user_model
    from .commands import submit, run
    from .integrations.telegram import download_voice
    from .integrations.voice import transcribe_audio
    with transaction.atomic():
        row = m.TelegramUpdate.objects.select_for_update().get(pk=update_id)
        if row.status != "pending":
            return
        row.status, row.started_at = "running", timezone.now()
        row.save(update_fields=["status", "started_at"])
    try:
        user = get_user_model().objects.get(is_active=True)
        if "callback_query" in row.payload:
            from .telegram_buttons import resolve
            from .commands import decide
            from .integrations.telegram import _call
            callback = row.payload["callback_query"]
            try:
                proposal, approve = resolve(user, callback["data"])
                outcome = decide(proposal, approve, proposal.revision, proposal.payload_digest)
                origin = proposal.action.command
                m.Delivery.objects.get_or_create(user=user, command=origin, position=1000 + proposal.revision,
                                                defaults={"destination": callback["chat_id"], "text": outcome.get("message", "Check the saved action outcome in the dashboard.")})
                answer = "The saved result is being delivered."
            except ValueError as exc:
                answer = str(exc)[:160]
            try:
                _call(settings.TELEGRAM_BOT_TOKEN, "answerCallbackQuery", json={"callback_query_id": callback["id"], "text": answer})
            except Exception:
                pass  # An expired loading indicator never replays an action.
            row.status, row.payload = "completed", {}
            row.save()
            return
        message = row.payload["message"]
        text = message.get("text", "")
        input_mode = row.payload.get("input_mode", "voice" if "voice" in message else "text")
        if "voice" in message:
            data = download_voice(settings.TELEGRAM_BOT_TOKEN, message["voice"]["file_id"])
            with TemporaryDirectory() as folder:
                path = Path(folder) / "voice.ogg"
                path.write_bytes(data)
                text = transcribe_audio(path, settings.WHISPER_MODEL)
        command, _ = submit(user, text, request_id=f"update-{row.update_id}", channel="telegram",
                            external_key=str(message["chat"]["id"]), input_mode=input_mode)
        command = run(command.id)
        row.status = "pending" if command.status == "queued" else "completed"
        row.payload = {"message": {"text": text, "chat": message["chat"]}, "input_mode": input_mode} if row.status == "pending" else {}
        for pk in command.deliveries.filter(status="pending").values_list("pk", flat=True):
            kick(deliver_command, str(pk))
    except Exception:
        row.status, row.payload = "needs_attention", {}
        logger.warning("Telegram command needs attention. update_id=%s", update_id)
    row.save()
