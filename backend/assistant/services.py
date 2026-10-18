import json
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from . import models as m
from .contracts import validate_workflow, RISKS
from .scheduling import validate_schedule, next_due
from .utils import audit, payload_digest, kick, BudgetGateway, decrypt_credentials, encrypt_credentials

def state(user):
    return m.AssistantState.objects.get_or_create(user=user)[0]

def prepare_task(user, data):
    if not isinstance(data, dict):
        raise ValueError("Task must be an object")
    kind = data.get("kind", "reminder")
    if kind not in {"reminder", "research", "workflow"}:
        raise ValueError("Task kind must be reminder, research or workflow")
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    required = {"reminder": "message", "research": "topic", "workflow": "workflow_id"}[kind]
    if not isinstance(payload.get(required), str) or not 1 <= len(payload[required]) <= 4000:
        raise ValueError(f"{kind} payload requires {required}")
    if kind == "workflow" and not m.Workflow.objects.filter(pk=payload[required], user=user).exists():
        raise ValueError("Unknown workflow")
    clean_payload = {required: payload[required]}
    if kind == "research":
        from .contracts import ResearchArgs
        clean_payload = ResearchArgs.model_validate(payload).model_dump()
    schedule = validate_schedule(data.get("schedule", {}))
    due = next_due(schedule)
    if due is None:
        raise ValueError("Choose a future time")
    return {"name": str(data.get("name") or kind)[:160], "kind": kind, "payload": clean_payload, "schedule": schedule}

def create_task(user, data):
    clean = prepare_task(user, data)
    task = m.ScheduledTask.objects.create(user=user, **clean, next_run_at=next_due(clean["schedule"]))
    audit(user, "task.created", task_id=str(task.id), kind=task.kind)
    return task

def create_workflow(user, data):
    if not isinstance(data, dict):
        raise ValueError("Workflow must be an object")
    if not str(data.get("name", "")).strip():
        raise ValueError("Workflow name is required")
    spec = validate_workflow(data)
    workflow = m.Workflow.objects.create(user=user, name=str(data["name"])[:160], description=str(data.get("description", ""))[:4000], **spec)
    audit(user, "workflow.drafted", workflow_id=str(workflow.id))
    return workflow

def enable_workflow(workflow):
    with transaction.atomic():
        workflow = m.Workflow.objects.select_for_update().get(pk=workflow.pk)
        validate_workflow({"steps": workflow.steps, "allowed_tools": workflow.allowed_tools, "allowed_domains": workflow.allowed_domains, "allowed_paths": workflow.allowed_paths, "trigger": workflow.trigger})
        workflow.enabled, workflow.reviewed_at = True, timezone.now()
        workflow.save()
        m.ScheduledTask.objects.filter(user=workflow.user, kind="workflow", payload__workflow_id=str(workflow.id)).delete()
        if workflow.trigger.get("kind") != "manual":
            create_task(workflow.user, {"name": workflow.name, "kind": "workflow", "payload": {"workflow_id": str(workflow.id)}, "schedule": workflow.trigger})
    audit(workflow.user, "workflow.enabled", workflow_id=str(workflow.id), version=workflow.version)
    return workflow

def start_run(workflow):
    if state(workflow.user).paused:
        raise ValueError("All automations are paused")
    if not workflow.enabled or not workflow.reviewed_at:
        raise ValueError("Review and enable the workflow first")
    spec = validate_workflow({"steps": workflow.steps, "allowed_tools": workflow.allowed_tools, "allowed_domains": workflow.allowed_domains, "allowed_paths": workflow.allowed_paths, "trigger": workflow.trigger})
    run = m.WorkflowRun.objects.create(user=workflow.user, workflow=workflow, snapshot={**spec, "name": workflow.name, "version": workflow.version})
    audit(workflow.user, "run.queued", run_id=str(run.id))
    from .tasks import execute_run
    kick(execute_run, str(run.id))
    return run

def run_allowed(run):
    return not state(run.user).paused and run.workflow and run.workflow.enabled and run.workflow.version == run.snapshot.get("version") and run.status not in {"cancelled", "completed", "failed"}

def request_approval(run, risk, job=None):
    if risk not in RISKS:
        raise ValueError("Unknown sensitive action class")
    binding = {"step": run.snapshot["steps"][run.step_index], "checkpoint": job.result.get("next_action", 0) if job else 0, "risk": risk}
    approval = m.Approval.objects.create(user=run.user, run=run, step_index=run.step_index, risk=risk, description=f"Approve {risk.replace('_', ' ')} for step {run.step_index + 1} of {run.snapshot['name']}", payload_digest=payload_digest(binding), expires_at=timezone.now() + timedelta(hours=24))
    run.status = "needs_approval"
    run.save(update_fields=["status", "updated_at"])
    audit(run.user, "approval.requested", approval_id=str(approval.id), risk=risk, run_id=str(run.id))
    return approval

def decide_approval(approval, approve):
    with transaction.atomic():
        approval = m.Approval.objects.select_for_update().get(pk=approval.pk)
        run = m.WorkflowRun.objects.select_for_update().get(pk=approval.run_id)
        if approval.status != "pending" or approval.expires_at < timezone.now() or run.step_index != approval.step_index or run.status != "needs_approval":
            raise ValueError("Approval is expired or no longer applies")
        if not run_allowed(run):
            raise ValueError("Resume the reviewed workflow and global automations before approving")
        job = m.DesktopJob.objects.filter(run=run, step_index=run.step_index).first()
        binding = {"step": run.snapshot["steps"][run.step_index], "checkpoint": job.result.get("next_action", 0) if job else 0, "risk": approval.risk}
        if approval.payload_digest != payload_digest(binding):
            raise ValueError("The action changed after approval was requested")
        approval.status = "approved" if approve else "rejected"
        approval.decided_at = timezone.now()
        approval.save()
        if approve and job:
            job.status, job.approved_risk = "queued", approval.risk
            job.args = {**job.args, "resume_index": job.result.get("next_action", 0)}
            job.save()
            run.status = "waiting_desktop"
        elif approve:
            run.status = "queued"
        else:
            run.status = "cancelled"
            if job:
                job.status = "cancelled"
                job.save()
        run.save()
    audit(run.user, "approval.decided", approval_id=str(approval.id), decision=approval.status)
    if approve and not job:
        from .tasks import execute_run
        kick(execute_run, str(run.id))
    return approval

def calendar_token(user):
    from .integrations.calendar import refresh_token
    credentials = decrypt_credentials(user, "google")
    if credentials.get("expires_at", 0) < timezone.now().timestamp() + 60:
        if not credentials.get("refresh_token"):
            raise ValueError("Reconnect Google Calendar; refresh authorization is unavailable")
        refreshed = refresh_token(settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, credentials["refresh_token"])
        credentials.update(refreshed)
        credentials["expires_at"] = timezone.now().timestamp() + refreshed.get("expires_in", 3600)
        encrypt_credentials(user, "google", credentials)
    return credentials["access_token"]

def tool_contracts():
    def function(name, description, properties, required=()):
        return {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": list(required)}}
    text = {"type": "string"}
    return [
        function("search_web", "Search current public internet information with sources", {"query": text}, ["query"]),
        function("run_deep_research", "Queue cited research and DOCX/PDF exports. Use report_kind=project_ideas for five enterprise software/AI project proposals ranked down to two detailed plans.", {"topic": text, "include_academic": {"type": "boolean"}, "report_kind": {"type": "string", "enum": ["standard", "project_ideas"]}}, ["topic"]),
        function("schedule_task", "Create a reminder or recurring research job. Ask if time is unclear. weekdays 0=Mon..6=Sun", {"name": text, "kind": {"type": "string", "enum": ["reminder", "research"]}, "payload": {"type": "object", "properties": {"message": text, "topic": text, "include_academic": {"type": "boolean"}, "report_kind": {"type": "string", "enum": ["standard", "project_ideas"]}}}, "schedule": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["once", "daily", "weekly"]}, "at": text, "time": text, "timezone": text, "weekdays": {"type": "array", "items": {"type": "integer"}}}}}, ["name", "kind", "payload", "schedule"]),
        function("calendar_list_events", "Read upcoming events from the connected owned calendar", {}, []),
        function("list_tasks", "List reminders and recurring tasks, with IDs for updating or pausing a specific task", {}),
        function("update_task", "Propose a task change for confirmation. Use the exact task_id from list_tasks; ask for ambiguous times.", {"task_id": text, "name": text, "payload": {"type": "object"}, "schedule": {"type": "object"}}, ["task_id"]),
        function("set_task_enabled", "Propose pausing or resuming a reminder/research task; never change workflow schedules through this tool", {"task_id": text, "enabled": {"type": "boolean"}}, ["task_id", "enabled"]),
        function("calendar_create_event", "Propose an owned-calendar event. Read back exact start/end and wait for user confirmation.", {"summary": text, "start": text, "end": text, "timezone": text, "description": text, "location": text, "calendar_id": text}, ["summary", "start", "end"]),
        function("calendar_update_event", "Propose changing a specific owned-calendar event. Use its exact event_id from calendar_list_events; never guess the event or AM/PM.", {"event_id": text, "summary": text, "start": text, "end": text, "timezone": text, "description": text, "location": text, "calendar_id": text}, ["event_id"]),
        function("draft_workflow", "Draft a workflow for user review. Never activate. Registered tools: file.list/read/write/move/delete, browser.run, calendar.create/update, research.run, notify. research.run args: topic, optional include_academic, report_kind (standard or project_ideas for five enterprise project proposals with two shortlisted plans). Each step has tool and args. Browser mutating actions require expected_url and expected_text; folders are absolute Windows paths. Ask for missing sites/folders first.", {"name": text, "description": text, "steps": {"type": "array", "items": {"type": "object", "properties": {"tool": text, "args": {"type": "object"}}, "required": ["tool", "args"]}}, "allowed_tools": {"type": "array", "items": text}, "allowed_domains": {"type": "array", "items": text}, "allowed_paths": {"type": "array", "items": text}, "trigger": {"type": "object", "properties": {"kind": text, "at": text, "time": text, "timezone": text, "weekdays": {"type": "array", "items": {"type": "integer"}}}}}, ["name", "steps", "allowed_tools", "allowed_domains", "allowed_paths"]),
    ]

def tools():
    """Compatibility export; runtime filtering lives in capabilities.model_tools."""
    return tool_contracts()


def turn(user, text, conversation_id=None, request_id=None, input_mode="text"):
    from .commands import submit, run, response_for
    command, _ = submit(user, text, conversation_id=conversation_id, request_id=request_id, input_mode=input_mode)
    command = run(command.id)
    return command.response or response_for(command, "Your command is queued behind the current conversation turn.")


def respond(command):
    from .capabilities import model_tools, system_context
    from .commands import execute_tool, response_for, ensure_active, cancellation_probe
    from .integrations.errors import ConfigError, ProviderError
    user, conversation = command.user, command.conversation
    m.Message.objects.create(conversation=conversation, role="user", content=command.input_text)
    response = response_for(command)
    from .builtins import answer
    builtin = answer(command)
    if builtin is not None:
        response.update(reply_text=builtin, handled_by="built_in")
        audit(user, "command.builtin", command_id=str(command.id))
        return response
    gateway = BudgetGateway(user, profile=command.model_profile)
    history = list(conversation.messages.order_by("-created_at", "-id").values("role", "content")[:20])[::-1]
    history.insert(0, {"role": "system", "content": f"Current local date/time: {timezone.localtime().isoformat()}; timezone {settings.TIME_ZONE}. " + system_context(user, command.model_profile, command.input_mode, command.channel)})
    ensure_active(command)
    result = gateway.chat(history, model_tools(user, command.model_profile), cancelled=cancellation_probe(command.id))
    ensure_active(command)
    outcomes = []
    for index, call in enumerate(result.get("tool_calls", [])[:4]):
        name, args = call.get("name"), call.get("args")
        try:
            outcome = execute_tool(command, index, name, args, gateway, response)
        except (ValueError, KeyError, ConfigError, ProviderError) as exc:
            message = str(exc) if not isinstance(exc, KeyError) else "The tool arguments are incomplete. Please clarify the request."
            outcome = {"message": message, "status": "failed"}
            m.ActionExecution.objects.filter(command=command, step=index).update(status="failed", result=outcome)
        safe_name = name if isinstance(name, str) and name in {item["name"] for item in tool_contracts()} else "unregistered"
        audit(user, "tool.dispatched", tool=safe_name, succeeded=outcome.get("status") != "failed", command_id=str(command.id))
        outcomes.append(outcome)
        if response["action_proposals"]:
            break
    if outcomes:
        # Server state supplies action readbacks and completion wording; no model rewrite.
        response["reply_text"] = "\n\n".join(item["message"] for item in outcomes)
        m.Message.objects.create(conversation=conversation, role="tool", content=json.dumps(outcomes, default=str)[:30000])
    else:
        response["reply_text"] = result.get("text", "") or "No response returned. Try rephrasing your request."
    return response
