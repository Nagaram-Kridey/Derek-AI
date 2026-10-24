"""Owner-scoped operations shared by dashboard and conversational adapters."""
import json
import uuid

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from . import models as m
from .utils import audit, kick, payload_digest

OPERATIONS = {"pause_all", "resume_all", "enable_workflow", "pause_workflow", "run_workflow", "edit_workflow", "cancel_run", "cancel_report", "send_report", "approve_step", "reject_step"}
SAFE_WHILE_PAUSED = {"pause_all", "resume_all", "pause_workflow", "edit_workflow", "cancel_run", "cancel_report", "reject_step"}


def owned(model, user, identifier, *, lock=False):
    try:
        identifier = uuid.UUID(str(identifier))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Use the exact item ID from its list.") from exc
    rows = model.objects.select_for_update() if lock else model.objects
    row = rows.filter(user=user, pk=identifier).first()
    if row is None:
        raise ValueError("That item was not found in your workspace.")
    return row


def definition(row):
    return {key: getattr(row, key) for key in ("name", "description", "steps", "allowed_tools", "allowed_domains", "allowed_paths", "trigger", "version", "enabled")}


def inspect(user, args):
    if set(args) - {"area", "item_id", "query"}:
        raise ValueError("Choose an area and optional exact item_id.")
    area, identifier = args.get("area"), args.get("item_id")
    query = args.get("query", "")
    if not isinstance(query, str) or len(query) > 160:
        raise ValueError("Search text must contain at most 160 characters.")
    if area == "workflows":
        if identifier:
            row = owned(m.Workflow, user, identifier)
            rendered = json.dumps(definition(row), ensure_ascii=False, default=str)
            if len(rendered) > 16000:
                return f"Workflow '{row.name}' ({row.id}) has a large definition. Review all steps and permissions in Automations; this chat cannot show it completely."
            return "Workflow " + str(row.id) + ":\n" + rendered
        rows = m.Workflow.objects.filter(user=user, name__icontains=query).order_by("-created_at")[:15]
        return "\n\n".join(f"{row.name}: {'enabled' if row.enabled else 'paused/draft'}; version {row.version}; ID {row.id}" for row in rows) or "No workflows yet. Describe one to create a draft."
    if area == "runs":
        rows = [owned(m.WorkflowRun, user, identifier)] if identifier else m.WorkflowRun.objects.filter(user=user, snapshot__name__icontains=query).order_by("-created_at")[:15]
        return "\n\n".join(f"{row.snapshot.get('name', 'Workflow')}: {row.status}; step {row.step_index + 1}; ID {row.id}" for row in rows) or "No workflow runs yet."
    if area == "approvals":
        if identifier:
            current, row = snapshot(user, "approve_step", identifier)
            return json.dumps(current, ensure_ascii=False)
        rows = m.Approval.objects.filter(user=user, status="pending", description__icontains=query, expires_at__gt=timezone.now()).order_by("-created_at")[:10]
        return "\n\n".join(f"{row.description}; risk {row.risk}; expires {row.expires_at.isoformat()}; ID {row.id}" for row in rows) or "No pending sensitive-step approvals."
    if area == "reports":
        rows = [owned(m.Report, user, identifier)] if identifier else m.Report.objects.filter(user=user, title__icontains=query).order_by("-created_at")[:10]
        return "\n\n".join(f"{row.title}: {row.status}; ID {row.id}; PDF {'ready' if row.pdf else 'not ready'}, DOCX {'ready' if row.docx else 'not ready'}. "
                           + ("Open Reports in the dashboard, or request send_report for a confirmed Telegram copy." if row.status == "completed" else str(row.progress.get("label", ""))) for row in rows) or "No reports yet."
    raise ValueError("Choose workflows, runs, approvals or reports.")


@transaction.atomic
def set_paused(user, paused):
    from .services import state
    if type(paused) is not bool:
        raise ValueError("paused must be true or false")
    row = m.AssistantState.objects.select_for_update().get(pk=state(user).pk)
    row.paused = paused
    row.save(update_fields=["paused"])
    audit(user, "control.pause", paused=paused)
    return row


def pause_workflow(row):
    row.enabled = False
    row.save(update_fields=["enabled"])
    m.ScheduledTask.objects.filter(user=row.user, kind="workflow", payload__workflow_id=str(row.id)).update(enabled=False)
    audit(row.user, "workflow.paused", workflow_id=str(row.id))
    return row


def cancel_workflow(row):
    runs = m.WorkflowRun.objects.filter(workflow=row).exclude(status__in=["completed", "failed", "cancelled"])
    m.DesktopJob.objects.filter(run__in=runs).exclude(status="completed").update(status="cancelled")
    m.Approval.objects.filter(run__in=runs, status="pending").update(status="rejected")
    runs.update(status="cancelled")
    m.ScheduledTask.objects.filter(user=row.user, kind="workflow", payload__workflow_id=str(row.id)).delete()


def workflow_change(row, values):
    from .contracts import validate_workflow
    fields = {"name", "description", "steps", "allowed_tools", "allowed_paths", "allowed_domains", "trigger"}
    if not isinstance(values, dict) or not values or set(values) - fields:
        raise ValueError("Choose workflow name, description, steps, permissions and/or trigger.")
    current = {key: getattr(row, key) for key in fields}
    merged = {**current, **values}
    name, description = merged["name"], merged["description"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160 or not isinstance(description, str) or len(description) > 4000:
        raise ValueError("Use a short workflow name and description.")
    return {**validate_workflow(merged), "name": name.strip(), "description": description}


def edit_workflow(row, values):
    clean = workflow_change(row, values)
    cancel_workflow(row)
    for key, value in clean.items():
        setattr(row, key, value)
    row.enabled, row.reviewed_at = False, None
    row.version += 1
    row.save()
    audit(row.user, "workflow.edited", workflow_id=str(row.id), version=row.version)
    return row


def cancel_run(row):
    m.DesktopJob.objects.filter(run=row).exclude(status="completed").update(status="cancelled")
    m.Approval.objects.filter(run=row, status="pending").update(status="rejected")
    if row.status not in {"completed", "failed"}:
        row.status = "cancelled"
        row.save()
        audit(row.user, "run.cancelled", run_id=str(row.id))
    return row


def cancel_report(row):
    if row.status in {"queued", "running"}:
        row.status = "cancelled"
        row.progress = {"stage": "cancelled", "label": "Research stopped"}
        row.save(update_fields=["status", "progress", "updated_at"])
        audit(row.user, "report.cancelled", report_id=str(row.id))
    return row


def send_report(row):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        raise ValueError("Configure the approved Telegram bot and private chat first.")
    if row.status != "completed" or not row.pdf:
        raise ValueError("The report PDF is not ready.")
    if row.progress.get("telegram_delivery", {}).get("status") in {"sending", "pending"}:
        raise ValueError("A PDF delivery is already queued or running.")
    row.progress = {**row.progress, "telegram_delivery": {"status": "pending", "due_at": timezone.now().isoformat()}}
    row.save(update_fields=["progress"])
    from .tasks import send_report_file
    transaction.on_commit(lambda: kick(send_report_file, str(row.id)))
    audit(row.user, "report.telegram_copy_requested", report_id=str(row.id))


def snapshot(user, operation, identifier=None, *, lock=False):
    from .services import state
    if operation in {"pause_all", "resume_all"}:
        row = state(user)
        if lock:
            row = m.AssistantState.objects.select_for_update().get(pk=row.pk)
        return {"paused": row.paused}, None
    if operation.endswith("workflow"):
        row = owned(m.Workflow, user, identifier, lock=lock)
        return {**definition(row), "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None}, row
    if operation in {"approve_step", "reject_step"}:
        row = owned(m.Approval, user, identifier, lock=lock)
        runs = m.WorkflowRun.objects.select_for_update() if lock else m.WorkflowRun.objects
        run = runs.get(pk=row.run_id, user=user)
        job = m.DesktopJob.objects.filter(run=run, step_index=row.step_index).first()
        return {"approval_id": str(row.id), "risk": row.risk, "status": row.status,
                "expires_at": row.expires_at.isoformat(), "payload_digest": row.payload_digest,
                "run_id": str(run.id), "run_status": run.status, "step_index": run.step_index,
                "reviewed_step": run.snapshot["steps"][row.step_index],
                "checkpoint": job.result.get("next_action", 0) if job else 0}, row
    model = m.WorkflowRun if operation == "cancel_run" else m.Report
    row = owned(model, user, identifier, lock=lock)
    return {"id": str(row.id), "status": row.status, "updated_at": row.updated_at.isoformat(),
            "delivery": row.progress.get("telegram_delivery", {}) if model == m.Report else None}, row


def prepare(user, args):
    from . import services
    if set(args) - {"operation", "item_id", "item_name", "definition"} or not isinstance(args.get("operation"), str) or args["operation"] not in OPERATIONS:
        raise ValueError("Choose a supported operation and an exact item_id when needed.")
    operation = args["operation"]
    if "definition" in args and operation != "edit_workflow":
        raise ValueError("Only edit_workflow accepts a changed definition.")
    identifier, name = args.get("item_id"), args.get("item_name")
    if identifier and name:
        raise ValueError("Choose one exact item ID or unique exact name.")
    if operation in {"pause_all", "resume_all"} and (identifier or name):
        raise ValueError("Global controls do not take a target item.")
    if name:
        if not isinstance(name, str) or not 1 <= len(name) <= 240:
            raise ValueError("Use a short exact item name.")
        if operation.endswith("workflow"):
            matches = m.Workflow.objects.filter(user=user, name__iexact=name)
        elif operation in {"cancel_report", "send_report"}:
            matches = m.Report.objects.filter(user=user, title__iexact=name)
        else:
            raise ValueError("Use the exact item ID for runs or approvals.")
        matches = list(matches[:2])
        if len(matches) != 1:
            raise ValueError("That name is missing or ambiguous. List the items and choose an exact ID.")
        identifier = str(matches[0].id)
    current, row = snapshot(user, operation, identifier)
    if services.state(user).paused and operation not in SAFE_WHILE_PAUSED:
        raise ValueError("Resume global automations first.")
    changes = None
    if operation == "edit_workflow":
        changes = workflow_change(row, args.get("definition"))
        label = f"Replace workflow '{row.name}' ({row.id}) with the following exact definition. It will be disabled, pending runs cancelled, and permission review required again:\n" + json.dumps(changes, ensure_ascii=False)
    elif operation in {"approve_step", "reject_step"}:
        if row.status != "pending" or row.expires_at <= timezone.now():
            raise ValueError("This step approval is expired or already resolved.")
        label = ("Approve this exact sensitive step once" if operation == "approve_step" else "Reject this sensitive step and stop its run") + ":\n" + json.dumps(current, ensure_ascii=False)
    elif operation == "enable_workflow":
        services.validate_workflow(definition(row))
        label = "Review and enable this exact workflow, including its trigger and all permissions/actions:\n" + json.dumps(definition(row), ensure_ascii=False, default=str)
    elif operation == "run_workflow":
        if not row.enabled or not row.reviewed_at:
            raise ValueError("Review and enable this workflow first.")
        label = f"Run the enabled workflow '{row.name}' once now.\n" + json.dumps(definition(row), ensure_ascii=False, default=str)
    elif operation == "pause_workflow":
        label = f"Pause workflow '{row.name}' ({row.id}). Future dispatch stops; an action already accepted externally may still finish."
    elif operation in {"pause_all", "resume_all"}:
        label = ("Pause all automations. Accepted external actions may still finish." if operation == "pause_all" else "Resume global automations. Already enabled workflows and due schedules can dispatch again.")
    elif operation == "cancel_run":
        if row.status in {"completed", "failed", "cancelled"}:
            raise ValueError("This run already has a final outcome; inspect it instead.")
        label = f"Cancel run '{row.snapshot.get('name', 'Workflow')}' ({row.id}), currently {row.status}. Accepted external actions cannot be undone."
    elif operation == "cancel_report":
        if row.status not in {"queued", "running"}:
            raise ValueError("This research already has a saved outcome; inspect it instead.")
        label = f"Stop research '{row.title}' ({row.id}), currently {row.status}. Provider usage already accepted may still count."
    else:
        if row.status != "completed" or not row.pdf:
            raise ValueError("The report PDF is not ready.")
        label = f"Send one PDF copy of '{row.title}' ({row.id}) to your configured approved Telegram chat. This may be an additional copy."
    cleaned = {"operation": operation, "item_id": str(row.id) if row else None,
               "expected": payload_digest(current)}
    if changes is not None:
        cleaned["definition"] = changes
    return cleaned, label


def apply(user, args):
    from . import services
    operation = args["operation"]
    current, row = snapshot(user, operation, args.get("item_id"), lock=True)
    if payload_digest(current) != args["expected"]:
        raise ValueError("The item changed after review. Request a fresh proposal.")
    if services.state(user).paused and operation not in SAFE_WHILE_PAUSED:
        raise ValueError("Resume global automations first.")
    if operation in {"pause_all", "resume_all"}:
        set_paused(user, operation == "pause_all")
    elif operation == "enable_workflow":
        services.enable_workflow(row)
    elif operation == "pause_workflow":
        pause_workflow(row)
    elif operation == "edit_workflow":
        edit_workflow(row, args["definition"])
    elif operation == "run_workflow":
        run = services.start_run(row)
        return {"message": f"Queued '{row.name}' once; execution is not yet complete. Run ID: {run.id}.", "run_id": str(run.id)}
    elif operation == "cancel_run":
        cancel_run(row)
    elif operation == "cancel_report":
        cancel_report(row)
    elif operation == "send_report":
        send_report(row)
    elif operation in {"approve_step", "reject_step"}:
        services.decide_approval(row, operation == "approve_step")
        return {"message": "Sensitive step approved once; execution is queued, not confirmed complete." if operation == "approve_step" else "Step rejected and run stopped.", "approval_id": str(row.id)}
    else:
        raise ValueError("Unsupported workspace control.")
    return {"message": {"pause_all": "All automations paused.", "resume_all": "Global automations resumed.",
                        "enable_workflow": "Reviewed workflow enabled.", "pause_workflow": "Workflow paused.",
                        "edit_workflow": "Workflow changes saved as a disabled draft. Pending runs were cancelled. Review and enable the new definition before it can run.",
                        "cancel_run": "Run cancellation saved; accepted external actions may still finish.",
                        "cancel_report": "Research stop saved; accepted provider usage may still count.",
                        "send_report": "PDF delivery queued to your approved Telegram chat."}[operation],
            "item_id": str(row.id) if row else None}
