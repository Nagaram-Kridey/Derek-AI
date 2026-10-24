"""Exact cross-channel shortcuts. Natural language also uses the same typed tools."""
import re
from django.db import transaction
from django.contrib.auth import get_user_model
from .utils import audit


def set_detail(user, value):
    from .chat_policy import DETAILS
    from .capabilities import preferences
    if value not in DETAILS:
        raise ValueError("Choose auto, brief, balanced or detailed.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        pref = preferences(user)
        pref.response_detail = value
        pref.save(update_fields=["response_detail"])
        audit(user, "preferences.response_detail", response_detail=value)
    return value


def local_reply(command):
    text = command.input_text.strip().casefold()
    if text == "/controls":
        return ("Shared controls for web chat, Telegram and online voice:\n\n"
                "/style auto|brief|balanced|detailed — shared answer detail\n"
                "/tasks · /workflows · /workflow ID · /runs · /reports · /approvals\n"
                "/enable ID · /pause-workflow ID · /run ID; ask naturally to edit a workflow\n"
                "/pause-all · /resume-all · /cancel-run ID · /cancel-report ID · /send-report ID\n\n"
                "/approve-step ID · /reject-step ID — exact sensitive-step review\n"
                "/memory on|off · /suggestions on|off · /model configured|gemini\n\n"
                "You can ask naturally too. State changes prepare an exact confirmation; inspect the full target and permissions first. Telegram uses the proposal buttons; online voice requires completed readback. /remember and /memories manage shared memory. Account linking, device pairing, bulk export/delete and Windows startup remain dashboard controls. Phone access is planned.")
    match = re.fullmatch(r"/style\s+(auto|brief|balanced|detailed)", text)
    if match:
        from .commands import ensure_active
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=command.user.pk)
            ensure_active(command)
            value = set_detail(command.user, match[1])
        return f"Answer detail set to {value} across normal web, Telegram and online voice chats. An explicit request for a short or detailed answer overrides it. Telegram still uses short bubbles."
    if text == "/style" or text.startswith("/style "):
        from .capabilities import preferences
        return f"Current answer detail: {preferences(command.user).response_detail}. Use /style auto, brief, balanced or detailed."
    match = re.fullmatch(r"/(memory|suggestions)\s+(on|off)", text)
    if match:
        from .capabilities import preferences
        from .commands import ensure_active
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=command.user.pk)
            ensure_active(command)
            pref = preferences(command.user)
            field = "memory_enabled" if match[1] == "memory" else "memory_suggestions"
            setattr(pref, field, match[2] == "on")
            pref.save(update_fields=[field])
            audit(command.user, "memory.preferences", **{field: match[2] == "on"})
        return f"Shared {match[1]} turned {match[2]}. Existing saved details remain available in Settings; private local history is separate."
    match = re.fullmatch(r"/model\s+(configured|gemini)", text)
    if match:
        from .capabilities import preferences
        from .commands import ensure_active
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=command.user.pk)
            ensure_active(command)
            pref = preferences(command.user)
            pref.interactive_profile = match[1]
            pref.save(update_fields=["interactive_profile"])
            audit(command.user, "preferences.updated", interactive_profile=match[1])
        return f"Model profile for new chats set to {match[1]}. Use /new to start with it; this conversation retains its pinned profile. The selected provider must be configured; no silent fallback."
    return None


def route(command):
    text = command.input_text.strip()
    lists = {"/workflows": "workflows", "/runs": "runs", "/reports": "reports", "/approvals": "approvals",
             "show my workflows": "workflows", "list my workflows": "workflows",
             "show my reports": "reports", "list my reports": "reports"}
    if text.casefold().rstrip(".!?") in lists:
        return {"tool_calls": [{"name": "inspect_workspace", "args": {"area": lists[text.casefold().rstrip(".!?")]}}]}
    match = re.fullmatch(r"/(workflow|report|run-status|approval)\s+([a-f0-9-]{36})", text, re.I)
    if match:
        return {"tool_calls": [{"name": "inspect_workspace", "args": {"area": {"workflow": "workflows", "report": "reports", "run-status": "runs", "approval": "approvals"}[match[1].lower()], "item_id": match[2]}}]}
    operation = {"/pause-all": "pause_all", "/resume-all": "resume_all",
                 "pause all automations": "pause_all", "resume all automations": "resume_all"}.get(text.casefold().rstrip(".!?"))
    if operation:
        args = {"operation": operation}
    else:
        match = re.fullmatch(r"/(enable|pause-workflow|run|cancel-run|cancel-report|send-report|approve-step|reject-step)\s+([a-f0-9-]{36})", text, re.I)
        if not match:
            return None
        args = {"operation": {"enable": "enable_workflow", "pause-workflow": "pause_workflow", "run": "run_workflow", "cancel-run": "cancel_run", "cancel-report": "cancel_report", "send-report": "send_report", "approve-step": "approve_step", "reject-step": "reject_step"}[match[1].lower()], "item_id": match[2]}
    return {"tool_calls": [{"name": "control_workspace", "args": args}]}
