import json
import secrets
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction, connection
from django.forms.models import model_to_dict
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from . import models as m, services
from .utils import audit, digest, encrypt_credentials, kick

def owned(model, request, pk):
    return get_object_or_404(model, user=request.user, pk=pk)

def data(row, exclude=()):
    out = model_to_dict(row, exclude=["user", *exclude])
    out.update(id=str(row.pk), created_at=row.created_at)
    return out

class LoginThrottle(SimpleRateThrottle):
    scope = "login"
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([LoginThrottle])
def login(request):
    user = authenticate(username=request.data.get("username", ""), password=request.data.get("password", ""))
    if not user:
        return Response({"detail": "Invalid username or password"}, status=401)
    if get_user_model().objects.filter(is_active=True).count() != 1:
        return Response({"detail": "This service supports one active user. Configure the owner account."}, status=503)
    token, _ = Token.objects.get_or_create(user=user)
    if settings.LOCAL_EXECUTION:
        from desktop.credentials import remember_owner_token
        remember_owner_token("http://127.0.0.1:8000", token.key, user.username)
    audit(user, "auth.login")
    return Response({"token": token.key, "username": user.username})

@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    if settings.LOCAL_EXECUTION:
        from desktop.credentials import forget_owner_token
        forget_owner_token("http://127.0.0.1:8000")
    audit(request.user, "auth.logout")
    return Response({"logged_out": True})

@api_view(["POST"])
def turn(request):
    text = request.data.get("text", "")
    if "audio" in request.FILES:
        audio = request.FILES["audio"]
        if audio.size > 20 * 1024 * 1024:
            raise ValueError("Audio uploads are limited to 20 MB")
        from .integrations.voice import transcribe_audio
        with TemporaryDirectory() as folder:
            path = Path(folder) / "recording.webm"
            with path.open("wb") as stream:
                for chunk in audio.chunks():
                    stream.write(chunk)
            text = transcribe_audio(path, settings.WHISPER_MODEL)
    return Response(services.turn(request.user, text, request.data.get("conversation_id") or None,
                                  request_id=request.data.get("request_id"), input_mode="voice" if "audio" in request.FILES else request.data.get("input_mode", "text")))

@api_view(["GET", "DELETE"])
def conversations(request, pk=None):
    if pk:
        row = owned(m.Conversation, request, pk)
        if request.method == "DELETE":
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                row = owned(m.Conversation, request, pk)
                if row.commands.filter(status__in=["running", "queued"]).exists() or m.ActionProposal.objects.filter(action__command__conversation=row, status="executing").exists():
                    return Response({"detail": "Wait for queued/running conversation turns before deleting this conversation."}, status=409)
                row.delete()
            return Response(status=204)
        return Response({**data(row), "messages": [{"id": msg.pk, "role": msg.role, "content": msg.content, "created_at": msg.created_at, **msg.metadata} for msg in row.messages.filter(role__in=["user", "assistant"])]})
    return Response([data(row) for row in m.Conversation.objects.filter(user=request.user).order_by("-created_at")[:200]])

@api_view(["GET", "POST", "DELETE", "PATCH"])
def scheduled_tasks(request, pk=None, action=None):
    if pk:
        row = owned(m.ScheduledTask, request, pk)
        if action == "history" and request.method == "GET":
            return Response([{**model_to_dict(item), "id": str(item.id), "created_at": item.created_at} for item in m.ScheduledOccurrence.objects.filter(task=row).order_by("-scheduled_for")[:30]])
        if request.method == "PATCH":
            if row.kind == "workflow":
                raise ValueError("Edit the workflow and review it in Automations before changing its trigger.")
            if set(request.data) - {"name", "payload", "schedule", "expected"}:
                raise ValueError("Only name, payload and schedule can be edited here.")
            with transaction.atomic():
                row = m.ScheduledTask.objects.select_for_update().get(pk=row.pk)
                if request.data.get("expected") and request.data["expected"] != task_version(row):
                    return Response({"detail": "This routine changed while you were editing it. Close the editor, refresh and review the current schedule."}, status=409)
                clean = services.prepare_task(request.user, {"kind": row.kind, "name": request.data.get("name", row.name), "payload": request.data.get("payload", row.payload), "schedule": request.data.get("schedule", row.schedule)})
                for key, value in clean.items():
                    setattr(row, key, value)
                from .scheduling import next_due
                row.next_run_at = next_due(row.schedule) if row.enabled else None
                row.save()
                m.ScheduledOccurrence.objects.filter(task=row, status="pending").update(status="cancelled")
                audit(request.user, "task.updated", task_id=str(row.pk))
            return Response({**data(row), "revision": task_version(row)})
        if request.method == "DELETE":
            with transaction.atomic():
                row = m.ScheduledTask.objects.select_for_update().get(pk=row.pk)
                if m.ScheduledOccurrence.objects.filter(task=row, status="running").exists():
                    return Response({"detail": "This routine is dispatching a saved occurrence. Wait for it to finish before deleting its history."}, status=409)
                row.delete()
            return Response(status=204)
        if action in {"pause", "resume"} and request.method == "POST":
            with transaction.atomic():
                row = m.ScheduledTask.objects.select_for_update().get(pk=row.pk)
                row.enabled = action == "resume"
                if row.enabled:
                    from .scheduling import next_due
                    row.next_run_at = next_due(row.schedule)
                    if row.next_run_at is None:
                        raise ValueError("One-off task is in the past; create a new task")
                row.save()
                if not row.enabled:
                    m.ScheduledOccurrence.objects.filter(task=row, status="pending").update(status="cancelled")
            audit(request.user, "task." + action, task_id=str(row.id))
            return Response(data(row))
        if request.method != "GET":
            return Response({"detail": "Use Edit, Pause or Resume for this routine."}, status=405)
        return Response({**data(row), "revision": task_version(row)})
    if request.method == "POST":
        from .form_requests import create_once
        row, created = create_once(request.user, "task", dict(request.data), m.ScheduledTask, lambda: services.create_task(request.user, request.data))
        return Response(data(row), status=201 if created else 200)
    if request.method != "GET":
        return Response({"detail": "Use POST to create a task."}, status=405)
    return Response([{**data(row), "revision": task_version(row)} for row in m.ScheduledTask.objects.filter(user=request.user).order_by("-created_at")[:200]])

def task_version(row):
    from .utils import payload_digest
    return payload_digest({"name": row.name, "kind": row.kind, "payload": row.payload, "schedule": row.schedule, "enabled": row.enabled})

@api_view(["GET", "POST", "PATCH", "DELETE"])
@transaction.atomic
def workflows(request, pk=None, action=None):
    if pk:
        row = get_object_or_404(m.Workflow.objects.select_for_update(), user=request.user, pk=pk)
        if request.method == "DELETE":
            cancel_workflow(row)
            row.delete()
            return Response(status=204)
        if action == "enable" and request.method == "POST":
            return Response(data(services.enable_workflow(row)))
        if action == "pause" and request.method == "POST":
            row.enabled = False
            row.save()
            m.ScheduledTask.objects.filter(user=row.user, kind="workflow", payload__workflow_id=str(row.id)).update(enabled=False)
            audit(row.user, "workflow.paused", workflow_id=str(row.id))
            return Response(data(row))
        if action == "run" and request.method == "POST":
            return Response(data(services.start_run(row)), status=202)
        if request.method == "PATCH":
            spec = {key: request.data.get(key, getattr(row, key)) for key in ["steps", "allowed_tools", "allowed_paths", "allowed_domains", "trigger"]}
            from .contracts import validate_workflow
            spec = validate_workflow(spec)
            cancel_workflow(row)
            for key, value in spec.items():
                setattr(row, key, value)
            row.name = str(request.data.get("name", row.name))[:160]
            row.description = str(request.data.get("description", row.description))[:4000]
            row.enabled, row.reviewed_at = False, None
            row.version += 1
            row.save()
            audit(row.user, "workflow.edited", workflow_id=str(row.id), version=row.version)
        return Response(data(row))
    if request.method == "POST":
        from .form_requests import create_once
        row, created = create_once(request.user, "workflow", dict(request.data), m.Workflow, lambda: services.create_workflow(request.user, request.data))
        return Response(data(row), status=201 if created else 200)
    return Response([data(row) for row in m.Workflow.objects.filter(user=request.user).order_by("-created_at")[:200]])

def cancel_workflow(workflow):
    runs = m.WorkflowRun.objects.filter(workflow=workflow).exclude(status__in=["completed", "failed", "cancelled"])
    m.DesktopJob.objects.filter(run__in=runs).exclude(status="completed").update(status="cancelled")
    m.Approval.objects.filter(run__in=runs, status="pending").update(status="rejected")
    runs.update(status="cancelled")
    m.ScheduledTask.objects.filter(user=workflow.user, kind="workflow", payload__workflow_id=str(workflow.id)).delete()

@api_view(["GET", "POST"])
@transaction.atomic
def runs(request, pk=None):
    if pk:
        run = get_object_or_404(m.WorkflowRun.objects.select_for_update(), user=request.user, pk=pk)
        if request.method == "POST":
            m.DesktopJob.objects.filter(run=run).exclude(status="completed").update(status="cancelled")
            m.Approval.objects.filter(run=run, status="pending").update(status="rejected")
            if run.status not in {"completed", "failed"}:
                run.status = "cancelled"
                run.save()
                audit(request.user, "run.cancelled", run_id=str(run.id))
        return Response(data(run))
    return Response([{**data(row), "workflow_name": row.snapshot.get("name", "") } for row in m.WorkflowRun.objects.filter(user=request.user).order_by("-created_at")[:200]])

@api_view(["GET", "POST"])
def approvals(request, pk=None, action=None):
    if pk:
        row = owned(m.Approval, request, pk)
        if action not in {"approve", "reject"} or request.method != "POST":
            raise ValueError("Choose approve or reject")
        return Response(data(services.decide_approval(row, action == "approve")))
    results = []
    for row in m.Approval.objects.filter(user=request.user, status="pending").select_related("run").order_by("-created_at")[:100]:
        step = row.run.snapshot["steps"][row.step_index]
        job = m.DesktopJob.objects.filter(run=row.run, step_index=row.step_index).first()
        checkpoint = job.result.get("next_action", 0) if job else 0
        actions = step["args"].get("actions", [])
        pending_action = actions[checkpoint] if type(checkpoint) is int and 0 <= checkpoint < len(actions) else step["args"]
        results.append({**data(row), "reason": row.description, "tool": step["tool"], "payload": {"checkpoint": checkpoint, "pending_action": pending_action, "reviewed_step": step}})
    return Response(results)

@api_view(["GET", "POST", "DELETE"])
def reports(request, pk=None, detail=False, action=None):
    if pk:
        row = owned(m.Report, request, pk)
        if request.method == "POST":
            if action == "deliver":
                if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
                    raise ValueError("Configure the approved Telegram bot and private chat before sending a report.")
                if request.data.get("confirm_copy") is not True:
                    raise ValueError("Confirm that you want a PDF copy sent to your approved Telegram chat.")
                with transaction.atomic():
                    row = m.Report.objects.select_for_update().get(pk=row.pk)
                    if row.status != "completed" or not row.pdf:
                        return Response({"detail": "The report PDF is not ready."}, status=409)
                    if row.progress.get("telegram_delivery", {}).get("status") in {"sending", "pending"}:
                        return Response({"detail": "A PDF delivery is already queued or running."}, status=409)
                    row.progress = {**row.progress, "telegram_delivery": {"status": "pending", "due_at": timezone.now().isoformat()}}
                    row.save(update_fields=["progress"])
                from .tasks import send_report_file
                kick(send_report_file, str(row.id))
                audit(request.user, "report.telegram_copy_requested", report_id=str(row.id))
                return Response({"queued": True}, status=202)
            if action != "cancel":
                return Response({"detail": "Use the report collection to request new research."}, status=405)
            changed = m.Report.objects.filter(pk=row.pk, status__in=["queued", "running"]).update(status="cancelled", progress={"stage": "cancelled", "label": "Research stopped"}, updated_at=timezone.now())
            if changed:
                audit(request.user, "report.cancelled", report_id=str(row.id))
            row.refresh_from_db()
            return Response({"status": row.status, "message": "Research stopped. Already accepted provider usage may still count." if changed else "The report already has a saved outcome."})
        if request.method == "DELETE":
            with transaction.atomic():
                row = m.Report.objects.select_for_update().get(pk=row.pk)
                if row.status == "running" or row.progress.get("telegram_delivery", {}).get("status") == "sending":
                    return Response({"detail": "Stop the research job or wait for it to finish before deleting"}, status=409)
                row.docx.delete(save=False)
                row.pdf.delete(save=False)
                row.delete()
            return Response(status=204)
        if detail:
            return Response({**data(row, ["docx", "pdf"]), "files": {"pdf": bool(row.pdf), "docx": bool(row.docx)}})
        fmt = request.query_params.get("format", "pdf")
        if fmt not in {"docx", "pdf"}:
            raise ValueError("Choose pdf or docx")
        file = getattr(row, fmt)
        if row.status != "completed" or not file:
            return Response({"detail": "Report file is not ready"}, status=409)
        return FileResponse(file.open("rb"), as_attachment=True, filename=f"Derek-{row.id}.{fmt}")
    if request.method == "POST":
        if services.state(request.user).paused:
            raise ValueError("Resume automations before requesting research.")
        from .contracts import ResearchArgs
        raw = dict(request.data)
        request_id = raw.pop("request_id", None)
        clean = ResearchArgs.model_validate(raw).model_dump()
        from .form_requests import create_once
        row, created = create_once(request.user, "report", {**clean, **({"request_id": request_id} if request_id is not None else {})}, m.Report,
                                   lambda: m.Report.objects.create(user=request.user, title=clean["topic"][:240], content=clean))
        from .tasks import research_report
        kick(research_report, str(row.id))
        if created:
            audit(request.user, "report.queued", report_id=str(row.id))
        return Response(data(row, ["docx", "pdf"]), status=202 if created else 200)
    return Response([{**data(row, ["docx", "pdf", "content"]), "summary": row.content.get("executive_summary", ""), "files": {"pdf": bool(row.pdf), "docx": bool(row.docx)}, "report_kind": row.content.get("report_kind", "standard")} for row in m.Report.objects.filter(user=request.user).order_by("-created_at")[:200]])

@api_view(["GET"])
def status(request):
    from .capabilities import profile_details, preferences
    from .local_status import runtime_status
    usage = m.UsageDay.objects.filter(user=request.user, date=timezone.localdate()).values("model_calls", "input_chars", "input_tokens", "output_tokens").first() or {}
    assistant_state = services.state(request.user)
    return Response({
        "runtime": runtime_status(),
        "paused": assistant_state.paused,
        "scheduler_online": bool(assistant_state.scheduler_heartbeat_at and assistant_state.scheduler_heartbeat_at > timezone.now()-timedelta(seconds=60)),
        "scheduler_last_seen": assistant_state.scheduler_heartbeat_at,
        "desktop_online": m.DesktopDevice.objects.filter(user=request.user, revoked=False, last_seen_at__gt=timezone.now()-timedelta(seconds=60)).exists(),
        "timezone": settings.TIME_ZONE,
        "pending_runs": m.WorkflowRun.objects.filter(user=request.user, status__in=["queued", "waiting_desktop"]).count(),
        "attention_needed": m.WorkflowRun.objects.filter(user=request.user, status="needs_attention").count(),
        "active_commands": m.Command.objects.filter(user=request.user, status__in=["queued", "running"]).count(),
        "pending_confirmations": m.ActionProposal.objects.filter(user=request.user, status="pending", expires_at__gt=timezone.now()).count(),
        "unread_notifications": m.Notification.objects.filter(user=request.user, read_at__isnull=True).count(),
        "interactive_model": profile_details(request.user, preferences(request.user).interactive_profile),
        "language_model": {"provider": settings.MODEL_PROVIDER, "model": settings.OLLAMA_MODEL if settings.MODEL_PROVIDER == "ollama" else settings.GEMINI_MODEL,
                           "local": settings.MODEL_PROVIDER == "ollama", "web_search": "public search snippets" if settings.MODEL_PROVIDER == "ollama" else "Google Search grounding"},
        "integrations": {"gemini": bool(settings.GEMINI_API_KEY), "ollama": settings.MODEL_PROVIDER == "ollama" and bool(settings.OLLAMA_MODEL), "telegram": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID), "cartesia": bool(settings.CARTESIA_API_KEY and settings.CARTESIA_VOICE_ID), "calendar": {"configured": bool(settings.GOOGLE_CLIENT_ID and settings.CREDENTIAL_ENCRYPTION_KEY), "connected": m.ProviderCredential.objects.filter(user=request.user, provider="google").exists()}},
        "usage": {**usage, "daily_call_limit": settings.DAILY_MODEL_CALL_LIMIT, "daily_input_char_limit": settings.DAILY_INPUT_CHAR_LIMIT},
    })

@api_view(["POST"])
def control(request):
    if type(request.data.get("paused")) is not bool:
        raise ValueError("paused must be true or false")
    row = services.state(request.user)
    row.paused = request.data["paused"]
    row.save()
    audit(request.user, "control.pause", paused=row.paused)
    return Response({"paused": row.paused})

@api_view(["GET"])
def activity(request):
    return Response([{**data(row), "action": row.event, "details": row.detail} for row in m.AuditEvent.objects.filter(user=request.user)[:300]])

@api_view(["GET", "POST"])
def notifications(request, pk=None):
    if request.method == "POST":
        rows = m.Notification.objects.filter(user=request.user, read_at__isnull=True)
        if pk:
            rows = rows.filter(pk=pk)
        rows.update(read_at=timezone.now())
        return Response({"read": True})
    return Response([data(row) for row in m.Notification.objects.filter(user=request.user).order_by("-created_at")[:100]])

@api_view(["GET", "POST", "DELETE"])
def devices(request, pk=None):
    if pk:
        device = owned(m.DesktopDevice, request, pk)
        device.revoked = True
        device.save()
        return Response({"revoked": True})
    if request.method == "POST":
        name = str(request.data.get("name", "Windows companion"))[:120]
        credential = secrets.token_urlsafe(48)
        device = m.DesktopDevice.objects.create(user=request.user, name=name, token_digest=digest(credential))
        audit(request.user, "device.paired", device_id=str(device.id))
        return Response({"id": str(device.id), "name": name, "credential": credential}, status=201)
    return Response([data(row, ["token_digest"]) for row in m.DesktopDevice.objects.filter(user=request.user)])

class DeviceAuth(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Device "):
            raise AuthenticationFailed("Device credential required")
        device = m.DesktopDevice.objects.select_related("user").filter(token_digest=digest(header[7:]), revoked=False, user__is_active=True).first()
        if not device:
            raise AuthenticationFailed("Invalid device credential")
        request.device = device
        m.DesktopDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
        return device.user, device
    def authenticate_header(self, request):
        return "Device"

@api_view(["POST"])
@authentication_classes([DeviceAuth])
def heartbeat(request):
    paused = services.state(request.user).paused
    jobs = m.DesktopJob.objects.filter(device=request.device, status="leased").select_related("run__workflow", "run__user")
    stop_ids = []
    for job in jobs:
        if paused or not services.run_allowed(job.run):
            stop_ids.append(str(job.id))
        else:
            m.DesktopJob.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now()+timedelta(minutes=2))
    return Response({"paused": paused, "stop_job_ids": stop_ids})

@api_view(["POST"])
@authentication_classes([DeviceAuth])
def claim_job(request):
    if services.state(request.user).paused:
        return Response({"job": None})
    with transaction.atomic():
        if m.DesktopJob.objects.filter(device=request.device, status="leased").exists():
            return Response({"job": None})
        for job in m.DesktopJob.objects.select_for_update(of=("self",)).filter(user=request.user, status="queued").select_related("run__workflow", "run__user").order_by("created_at")[:20]:
            if not services.run_allowed(job.run):
                continue
            token = secrets.token_urlsafe(32)
            job.status, job.device, job.lease_digest = "leased", request.device, digest(token)
            job.lease_expires_at = timezone.now()+timedelta(minutes=2)
            job.save()
            audit(request.user, "desktop.leased", job_id=str(job.id), device_id=str(request.device.id))
            return Response({"job": {"id": str(job.id), "lease_token": token, "tool": job.tool, "args": job.args, "policy": job.policy, "approved_risk": job.approved_risk}})
    return Response({"job": None})

@api_view(["POST"])
@authentication_classes([DeviceAuth])
def complete_job(request, pk):
    with transaction.atomic():
        job = owned(m.DesktopJob, request, pk)
        job = m.DesktopJob.objects.select_for_update().get(pk=job.pk)
        if job.device_id != request.device.id or not secrets.compare_digest(job.lease_digest, digest(str(request.data.get("lease_token", "")))):
            raise AuthenticationFailed("Invalid job lease")
        if job.status == "completed":
            return Response({"accepted": True})
        if job.status != "leased" or job.lease_expires_at < timezone.now():
            return Response({"detail": "Job lease is no longer active; do not replay the operation"}, status=409)
        result = request.data.get("result", {})
        status = request.data.get("status")
        if status not in {"completed", "failed", "needs_approval", "needs_attention"} or not isinstance(result, dict) or len(json.dumps(result)) > 200000:
            raise ValueError("Invalid job result")
        run = m.WorkflowRun.objects.select_for_update().get(pk=job.run_id)
        job.status, job.result, job.error, job.approved_risk = status, result, str(request.data.get("error", ""))[:4000], None
        job.save()
        if run.status == "cancelled":
            return Response({"accepted": True})
        if status == "needs_approval":
            risk = request.data.get("risk")
            services.request_approval(run, risk, job)
        elif status == "completed":
            run.results.append({"tool": job.tool, "result": result})
            run.step_index += 1
            run.status = "completed" if run.step_index >= len(run.snapshot["steps"]) else "queued"
            run.save()
        else:
            run.status, run.error = status, job.error
            run.save()
    audit(request.user, "desktop.result", job_id=str(job.id), status=status)
    if run.status == "queued":
        from .tasks import execute_run
        kick(execute_run, str(run.id))
    return Response({"accepted": True, "status": run.status})

@api_view(["POST"])
def calendar_connect(request):
    from .integrations.calendar import build_auth_url
    if not settings.GOOGLE_CLIENT_ID or not settings.CREDENTIAL_ENCRYPTION_KEY:
        raise ValueError("Configure Google OAuth and credential encryption first")
    token = secrets.token_urlsafe(32)
    m.OAuthState.objects.create(user=request.user, digest=digest(token), expires_at=timezone.now()+timedelta(minutes=10))
    return Response({"url": build_auth_url(settings.GOOGLE_CLIENT_ID, settings.GOOGLE_REDIRECT_URI, token)})

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def calendar_callback(request):
    from .integrations.calendar import exchange_code
    with transaction.atomic():
        row = m.OAuthState.objects.select_for_update().filter(digest=digest(request.query_params.get("state", "")), expires_at__gt=timezone.now()).first()
        if not row:
            raise ValueError("OAuth request expired or invalid")
        user = row.user
        row.delete()
    code = request.query_params.get("code", "")
    if not code:
        raise ValueError("Google authorization was not completed")
    credentials = exchange_code(settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, settings.GOOGLE_REDIRECT_URI, code)
    if "https://www.googleapis.com/auth/calendar.events.owned" not in credentials.get("scope", "").split():
        raise ValueError("Required owned-calendar permission was not granted")
    credentials["expires_at"] = timezone.now().timestamp()+credentials.get("expires_in", 3600)
    encrypt_credentials(user, "google", credentials)
    audit(user, "calendar.connected")
    return HttpResponse('<p>Google Calendar connected. Return to your <a href="/">Derek workspace</a>.</p>')

@api_view(["GET", "DELETE"])
def calendar_events(request):
    if request.method == "DELETE":
        m.ProviderCredential.objects.filter(user=request.user, provider="google").delete()
        return Response({"disconnected": True})
    from .integrations.calendar import list_events
    result = list_events(services.calendar_token(request.user))
    return Response(result.get("items", []) if isinstance(result, dict) else result)

@api_view(["GET"])
def export_data(request):
    payload = {
        "schema_version": 1,
        "exported_at": timezone.now(),
        "timezone": settings.TIME_ZONE,
        "scope": "Normal assistant records only. Download report attachments separately; private local chat has its own export. Credentials are excluded.",
        "conversations": [{**data(row), "messages": list(row.messages.values("role", "content", "metadata", "created_at"))}
                          for row in m.Conversation.objects.filter(user=request.user)],
        "reports": [data(row, ["docx", "pdf"]) for row in m.Report.objects.filter(user=request.user)],
        "preferences": m.AssistantPreferences.objects.filter(user=request.user).values("interactive_profile", "telegram_voice_replies").first(),
        "occurrences": [data(row) for row in m.ScheduledOccurrence.objects.filter(task__user=request.user)],
        "command_events": [data(row) for row in m.CommandEvent.objects.filter(command__user=request.user)],
    }
    for name, model in {
        "tasks": m.ScheduledTask, "workflows": m.Workflow, "workflow_runs": m.WorkflowRun,
        "notifications": m.Notification, "audit": m.AuditEvent, "commands": m.Command,
        "actions": m.ActionExecution, "action_proposals": m.ActionProposal, "deliveries": m.Delivery,
    }.items():
        payload[name] = [data(row) for row in model.objects.filter(user=request.user)]
    return Response(payload, headers={"Content-Disposition": 'attachment; filename="derek-export.json"'})

@api_view(["DELETE"])
def delete_history(request):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if (m.Command.objects.filter(user=request.user, status__in=["queued", "running"]).exists()
                or m.ActionProposal.objects.filter(user=request.user, status="executing").exists()):
            return Response({"detail": "Wait for queued/running conversation turns before deleting history."}, status=409)
        m.Conversation.objects.filter(user=request.user).delete()
    audit(request.user, "history.deleted")
    return Response({"deleted": True})

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([])
def telegram_webhook(request):
    if not settings.TELEGRAM_WEBHOOK_SECRET or not secrets.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), settings.TELEGRAM_WEBHOOK_SECRET):
        return Response(status=403)
    if not isinstance(request.data, dict):
        return Response({"ok": False}, status=400)
    from .telegram_ingress import store_update
    row, created = store_update(request.data)
    if created:
        from .tasks import process_telegram
        kick(process_telegram, row.update_id)
    return Response({"ok": True})

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok"})

def dashboard(request):
    path = settings.BASE_DIR / "staticapp" / "index.html"
    if path.exists():
        return HttpResponse(path.read_text(encoding="utf-8"))
    return HttpResponse("Derek backend is running. Start the dashboard with npm run dev in web_dashboard.")
