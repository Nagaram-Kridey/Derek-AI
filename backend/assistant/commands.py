"""Durable commands, proposal-bound writes and independent channel delivery.

Running/uncertain work is never silently executed again after a crash.
"""

import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from . import models as m
from .integrations.errors import ConfigError, ProviderError, RequestCancelled
from .utils import audit, kick, payload_digest

FINAL = {"completed", "awaiting_confirmation", "failed", "needs_attention", "cancelled"}


def event(command, kind, **detail):
    m.CommandEvent.objects.create(command=command, kind=kind, detail=detail)


def proposal_data(proposal):
    return {
        "id": str(proposal.id),
        "revision": proposal.revision,
        "payload_digest": proposal.payload_digest,
        "readback": proposal.readback,
        "status": "expired"
        if proposal.status == "pending" and proposal.expires_at <= timezone.now()
        else proposal.status,
        "expires_at": proposal.expires_at.isoformat(),
    }


def command_data(command):
    response, status = dict(command.response), command.status
    if response.get("action_proposals"):
        proposals = list(
            m.ActionProposal.objects.filter(action__command=command).select_related(
                "action"
            )
        )
        response["action_proposals"] = [
            proposal_data(proposal) for proposal in proposals
        ]
        if (
            status == "awaiting_confirmation"
            and proposals
            and not any(
                proposal.status in {"pending", "executing"}
                and proposal.expires_at > timezone.now()
                for proposal in proposals
            )
        ):
            status = "completed"
            response["status"] = status
            response["reply_text"] = (
                "This confirmation expired. No change was made. Ask again for a fresh proposal."
                if proposals[-1].status == "pending"
                else proposals[-1].action.result.get(
                    "message",
                    "This readback is no longer pending. Ask again for a new proposal.",
                )
            )
    return {
        "command_id": str(command.id),
        "conversation_id": str(command.conversation_id),
        "status": status,
        "model_profile": command.model_profile,
        "reply_text": response.get("reply_text", ""),
        "response": response,
        "error": command.error,
        "created_at": command.created_at.isoformat(),
        "request_id": command.request_id,
        "input_text": command.input_text,
        "channel": command.channel,
        "started_at": command.started_at.isoformat() if command.started_at else None,
        "finished_at": command.finished_at.isoformat() if command.finished_at else None,
    }


def response_for(command, text=""):
    return {
        "reply_text": text,
        "command_id": str(command.id),
        "conversation_id": str(command.conversation_id),
        "status": command.status,
        "citations": [],
        "artifacts": [],
        "job_id": None,
        "approval_needed": None,
        "action_proposals": [],
        "search_suggestions_html": [],
    }


def invalidate_proposals(conversation_id):
    """A replaced readback cannot become an empty or reusable confirmation."""
    with transaction.atomic():
        owner_id = (
            m.Conversation.objects.filter(pk=conversation_id)
            .values_list("user_id", flat=True)
            .first()
        )
        if owner_id is None:
            return
        get_user_model().objects.select_for_update().get(pk=owner_id)
        proposals = m.ActionProposal.objects.select_for_update().filter(
            action__command__conversation_id=conversation_id, status="pending"
        )
        for proposal in proposals:
            proposal.status, proposal.decided_at = "cancelled", timezone.now()
            proposal.save(update_fields=["status", "decided_at"])
            m.ActionExecution.objects.filter(
                pk=proposal.action_id, status="awaiting_confirmation"
            ).update(
                status="cancelled",
                result={
                    "message": "This readback was replaced by a new request. No change was made.",
                    "status": "cancelled",
                },
            )


def expire_proposals(now):
    for identifier in m.ActionProposal.objects.filter(
        status="pending", expires_at__lte=now
    ).values_list("pk", flat=True)[:100]:
        with transaction.atomic():
            proposal = (
                m.ActionProposal.objects.select_for_update()
                .filter(pk=identifier)
                .first()
            )
            if not proposal or proposal.status != "pending":
                continue
            proposal.status, proposal.decided_at = "expired", now
            proposal.save(update_fields=["status", "decided_at"])
            action = m.ActionExecution.objects.select_for_update().get(
                pk=proposal.action_id
            )
            action.status = "expired"
            action.result = {
                "message": "This confirmation expired. No change was made. Ask again for a fresh proposal.",
                "status": "expired",
            }
            action.save(update_fields=["status", "result"])
        record_decision(action, proposal, action.result, False)


def submit(
    user,
    text,
    *,
    request_id=None,
    conversation_id=None,
    profile=None,
    input_mode="text",
    channel="web",
    external_key=None,
):
    from .capabilities import preferences

    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 12000:
        raise ValueError("Enter 1-12000 characters.")
    if input_mode not in {"text", "voice"} or channel not in {"web", "telegram"}:
        raise ValueError("Unsupported input mode or channel.")
    request_id = str(request_id or uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", request_id):
        raise ValueError(
            "request_id must contain 1-128 letters, digits, underscores, colons or hyphens."
        )
    if profile not in {None, "gemini", "configured"}:
        raise ValueError(
            "Choose gemini or configured; private chat is a separate desktop mode."
        )
    fingerprint = payload_digest(
        {
            "text": text.strip(),
            "conversation": str(conversation_id or ""),
            "profile": profile,
            "input_mode": input_mode,
        }
    )
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = m.Command.objects.filter(
            user=user, channel=channel, request_id=request_id
        ).first()
        if previous:
            if previous.fingerprint != fingerprint:
                raise ValueError(
                    "This request ID belongs to a different command. Retry the original request or use a new ID."
                )
            return previous, False
        session = None
        if channel == "telegram":
            if not external_key:
                raise ValueError("A verified Telegram identity is required.")
            session, _ = m.ChannelSession.objects.get_or_create(
                user=user, channel=channel, external_key=str(external_key)
            )
            session = m.ChannelSession.objects.select_for_update().get(pk=session.pk)
            if text.strip() == "/new":
                if session.conversation_id:
                    invalidate_proposals(session.conversation_id)
                session.conversation = None
            conversation_id = session.conversation_id
        if conversation_id and text.strip().casefold() == "/new":
            previous_conversation = m.Conversation.objects.filter(
                user=user, pk=conversation_id
            ).first()
            if not previous_conversation:
                raise ValueError("Unknown conversation.")
            invalidate_proposals(previous_conversation.pk)
            profile = profile or previous_conversation.model_profile
            conversation_id = None
        if conversation_id:
            conversation = m.Conversation.objects.filter(
                user=user, pk=conversation_id
            ).first()
            if not conversation:
                raise ValueError("Unknown conversation.")
            if profile and profile != conversation.model_profile:
                raise ValueError(
                    "Start a new conversation to change the model profile."
                )
        else:
            conversation = m.Conversation.objects.create(
                user=user,
                title=text[:100],
                model_profile=profile or preferences(user).interactive_profile,
            )
        if session:
            session.conversation = conversation
            session.save(update_fields=["conversation"])
        command = m.Command.objects.create(
            user=user,
            conversation=conversation,
            channel=channel,
            request_id=request_id,
            fingerprint=fingerprint,
            input_text=text.strip(),
            input_mode=input_mode,
            model_profile=conversation.model_profile,
        )
        if m.CommandCancellation.objects.filter(
            user=user,
            channel=channel,
            request_id=request_id,
            created_at__gt=timezone.now() - timedelta(days=1),
        ).exists():
            command.status, command.finished_at = "cancelled", timezone.now()
            command.response = response_for(
                command, "This request was cancelled. No new action was started."
            )
            command.save(update_fields=["status", "response", "finished_at"])
        event(command, command.status)
        audit(
            user,
            "command." + command.status,
            command_id=str(command.id),
            channel=channel,
        )
    return command, True


def ensure_active(command):
    if not m.Command.objects.filter(pk=command.pk, status="running").exists():
        raise RequestCancelled("Command cancelled.")


def cancellation_probe(command_id):
    def cancelled():
        # The provider polls this in a helper thread; never leak its DB connection.
        from django.db import connection

        try:
            return not m.Command.objects.filter(
                pk=command_id, status="running"
            ).exists()
        finally:
            if not connection.in_atomic_block:
                connection.close()

    return cancelled


def cancel_request(user, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[A-Za-z0-9:_-]{1,128}", request_id
    ):
        raise ValueError("Provide the original request_id.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        cancellation, _ = m.CommandCancellation.objects.get_or_create(
            user=user, channel="web", request_id=request_id
        )
        m.CommandCancellation.objects.filter(pk=cancellation.pk).update(
            created_at=timezone.now()
        )
        command = (
            m.Command.objects.select_for_update()
            .filter(user=user, channel="web", request_id=request_id)
            .first()
        )
        if not command:
            return {
                "status": "cancelled",
                "message": "Request cancelled before acceptance.",
                "command_id": None,
                "effects_may_continue": False,
            }
        executing = command.actions.filter(status="running").exists()
        committed = (
            command.actions.filter(status="committed")
            .exclude(tool__in=["search_web", "list_tasks", "calendar_list_events"])
            .exists()
        )
        if command.status not in {
            "completed",
            "failed",
            "needs_attention",
            "cancelled",
        }:
            command.actions.filter(status="pending").update(
                status="cancelled",
                result={"message": "Cancelled before dispatch.", "status": "cancelled"},
            )
            proposals = m.ActionProposal.objects.select_for_update().filter(
                action__command=command, status="pending"
            )
            for proposal in proposals:
                proposal.status, proposal.decided_at = "cancelled", timezone.now()
                proposal.save(update_fields=["status", "decided_at"])
                m.ActionExecution.objects.filter(
                    pk=proposal.action_id, status="awaiting_confirmation"
                ).update(
                    status="cancelled",
                    result={
                        "message": "Cancelled before confirmation.",
                        "status": "cancelled",
                    },
                )
            # A confirmation may have claimed its proposal while cancellation
            # waited for that lock. Re-read before promising no effects.
            executing = command.actions.filter(status="running").exists()
            committed = (
                command.actions.filter(status="committed")
                .exclude(tool__in=["search_web", "list_tasks", "calendar_list_events"])
                .exists()
            )
            command.status, command.finished_at = "cancelled", timezone.now()
            message = (
                "Response stopped. Work already saved or executing may continue; check Activity."
                if executing or committed
                else "Cancelled. No new action will be started."
            )
            command.response = response_for(command, message)
            command.save(update_fields=["status", "response", "finished_at"])
            m.Message.objects.create(
                conversation_id=command.conversation_id,
                role="assistant",
                content=message,
                metadata={"command_id": str(command.id), "status": "cancelled"},
            )
            event(command, "cancelled", effects_may_continue=executing or committed)
            audit(
                user,
                "command.cancelled",
                command_id=str(command.id),
                effects_may_continue=executing or committed,
            )
        return {
            **command_data(command),
            "message": command.response.get(
                "reply_text", "Check the saved command outcome."
            ),
            "effects_may_continue": executing or committed,
        }


def run(command_id):
    from . import services

    owner_id = (
        m.Command.objects.filter(pk=command_id)
        .values_list("user_id", flat=True)
        .first()
    )
    if owner_id is None:
        return None
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner_id)
        command = (
            m.Command.objects.select_for_update()
            .select_related("user")
            .get(pk=command_id)
        )
        if command.status != "queued":
            return command
        m.Conversation.objects.select_for_update().get(pk=command.conversation_id)
        if (
            m.Command.objects.filter(
                conversation_id=command.conversation_id, status="running"
            )
            .exclude(pk=command.pk)
            .exists()
        ):
            return command
        earlier = m.Command.objects.filter(
            conversation_id=command.conversation_id,
            status="queued",
            created_at__lt=command.created_at,
        ).exists()
        if earlier:
            return command
        command.status, command.started_at = "running", timezone.now()
        command.save(update_fields=["status", "started_at"])
        event(command, "running")
    try:
        ensure_active(command)
        pending = (
            m.ActionProposal.objects.filter(
                action__command__conversation_id=command.conversation_id,
                status="pending",
            )
            .order_by("-created_at")
            .first()
        )
        control = command.input_text.lower().strip().rstrip(".!?")
        if control == "/new":
            result = response_for(
                command, "New conversation started. What would you like to do?"
            )
            m.Message.objects.create(
                conversation_id=command.conversation_id,
                role="user",
                content=command.input_text,
            )
        elif (
            control in {"yes", "confirm", "yes please", "cancel", "no", "no thanks"}
            and pending
            and (command.input_mode == "voice" or command.channel == "telegram")
        ):
            result = response_for(
                command,
                "Use the Confirm change or Cancel button on the exact proposal in Telegram."
                if command.channel == "telegram"
                else "Use the current proposal's confirmation control after its complete readback. Voice input alone cannot confirm a different or interrupted proposal.",
            )
            m.Message.objects.create(
                conversation_id=command.conversation_id,
                role="user",
                content=command.input_text,
            )
        elif (
            control in {"yes", "confirm", "yes please", "cancel", "no", "no thanks"}
            and pending
        ):
            outcome = decide(
                pending,
                control in {"yes", "confirm", "yes please"},
                pending.revision,
                pending.payload_digest,
                persist_message=False,
            )
            result = response_for(command, outcome["message"])
            m.Message.objects.create(
                conversation_id=command.conversation_id,
                role="user",
                content=command.input_text,
            )
        else:
            # A new request invalidates the previous readback; an old 'yes' cannot confirm it later.
            invalidate_proposals(command.conversation_id)
            result = services.respond(command)
        command.status = (
            "awaiting_confirmation" if result.get("action_proposals") else "completed"
        )
        result["status"] = command.status
        command.response = result
    except RequestCancelled:
        return m.Command.objects.filter(pk=command.pk).first()
    except Exception as exc:
        command.status = (
            "failed"
            if isinstance(exc, (ValueError, ConfigError, ProviderError))
            else "needs_attention"
        )
        command.error = (
            str(exc)[:1500]
            if isinstance(exc, (ValueError, ConfigError, ProviderError))
            else "Command interrupted. Inspect Activity before creating another action."
        )
        command.response = response_for(command, command.error)
        command.response["status"] = command.status
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=command.user_id)
        current = m.Command.objects.select_for_update().filter(pk=command.pk).first()
        if not current or current.status == "cancelled":
            return current
        command.finished_at = timezone.now()
        command.save(update_fields=["status", "response", "error", "finished_at"])
        m.Message.objects.create(
            conversation_id=command.conversation_id,
            role="assistant",
            content=command.response["reply_text"],
            metadata={
                key: value
                for key, value in command.response.items()
                if key not in {"reply_text", "conversation_id"}
            },
        )
        event(
            command,
            command.status,
            reply_text=command.response["reply_text"],
            response=command.response,
        )
        if command.channel == "telegram":
            session = m.ChannelSession.objects.filter(
                user=command.user,
                channel="telegram",
                conversation_id=command.conversation_id,
            ).first()
            if session:
                for position, text in enumerate(
                    telegram_blocks(command.response["reply_text"])
                ):
                    m.Delivery.objects.get_or_create(
                        user=command.user,
                        command=command,
                        position=position,
                        defaults={"destination": session.external_key, "text": text},
                    )
        audit(
            command.user,
            "command.finished",
            command_id=str(command.id),
            status=command.status,
        )
    return command


def telegram_blocks(text):
    # Paragraphs/sentences remain intact where possible; the full answer stays in history.
    parts = re.split(r"\n\s*\n|(?<=[.!?])\s+", text.strip())
    blocks, current = [], ""
    for part in parts:
        if len(current) + len(part) + 2 <= 1000:
            current = (current + "\n\n" + part).strip()
        else:
            if current:
                blocks.append(current)
            while len(part) > 1000:
                split = part.rfind(" ", 0, 1000)
                split = split if split > 0 else 1000
                blocks.append(part[:split])
                part = part[split:].lstrip()
            current = part
    if current:
        blocks.append(current)
    if len(blocks) > 3:
        return blocks[:2] + [
            blocks[2][:850]
            + "\n\nThe full reply is saved in your dashboard conversation."
        ]
    return blocks or ["No response text is available. Check Activity."]


def _task_snapshot(task):
    return {
        "name": task.name,
        "kind": task.kind,
        "payload": task.payload,
        "schedule": task.schedule,
        "enabled": task.enabled,
    }


def _schedule_label(schedule):
    zone = schedule["timezone"]
    if schedule["kind"] == "once":
        moment = datetime.fromisoformat(schedule["at"]).astimezone(ZoneInfo(zone))
        return moment.strftime("%A, %d %B %Y at %I:%M %p") + " (" + zone + ")"
    days = (
        "every day"
        if schedule["kind"] == "daily"
        else "every "
        + ", ".join(
            [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ][i]
            for i in schedule["weekdays"]
        )
    )
    return f"{days} at {schedule['time']} ({zone})"


def _calendar_time(value):
    if value.get("date"):
        return value["date"] + " (all day)"
    moment = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    zone = value.get("timeZone")
    if zone:
        moment = moment.astimezone(ZoneInfo(zone))
    return (
        moment.strftime("%A, %d %B %Y at %I:%M %p")
        + " ("
        + (zone or str(moment.tzinfo))
        + ")"
    )


def _task_content(task):
    if task["kind"] == "reminder":
        return "Message: " + task["payload"]["message"] + "."
    payload = task["payload"]
    return (
        "Research topic: "
        + payload["topic"]
        + ". Report: "
        + payload.get("report_kind", "standard")
        + ("; include academic sources." if payload.get("include_academic") else ".")
    )


def _require_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Use the exact task ID from the task list.") from exc


def prepare(action):
    from . import services

    args = action.args.copy()
    if action.tool == "schedule_task":
        if args.get("kind", "reminder") not in {"reminder", "research"}:
            raise ValueError("Workflow schedules require review in Automations.")
        args = services.prepare_task(action.user, args)
        label = (
            f"Create {args['kind']} '{args['name']}' for {_schedule_label(args['schedule'])}. "
            + _task_content(args)
        )
    elif action.tool in {"update_task", "set_task_enabled"}:
        task = m.ScheduledTask.objects.filter(
            user=action.user,
            pk=_require_uuid(args.get("task_id")),
            kind__in=["reminder", "research"],
        ).first()
        if not task:
            raise ValueError(
                "Choose a reminder or research task from your scheduled tasks; workflow schedules require Automations review."
            )
        expected = payload_digest(_task_snapshot(task))
        if action.tool == "update_task":
            if not set(args).intersection({"name", "payload", "schedule"}):
                raise ValueError("Say what to change about this task.")
            data = {
                **_task_snapshot(task),
                **{
                    key: value
                    for key, value in args.items()
                    if key in {"name", "payload", "schedule"}
                },
            }
            args = {
                "task_id": str(task.id),
                "expected": expected,
                "task": services.prepare_task(action.user, data),
            }
            label = (
                f"Update '{task.name}' to '{args['task']['name']}' for {_schedule_label(args['task']['schedule'])}. "
                + _task_content(args["task"])
            )
        else:
            if type(args.get("enabled")) is not bool:
                raise ValueError("enabled must be true or false.")
            args = {
                "task_id": str(task.id),
                "expected": expected,
                "enabled": args["enabled"],
            }
            label = f"{'Resume' if args['enabled'] else 'Pause'} '{task.name}'."
    elif action.tool in {"calendar_create_event", "calendar_update_event"}:
        from .integrations.calendar import validate_event, get_event

        if action.tool == "calendar_create_event":
            body = validate_event(args)
            body["id"] = action.id.hex
            args = {"calendar_id": args.get("calendar_id", "primary"), **body}
            detail = "; ".join(
                f"{key}: {body[key]}"
                for key in ("location", "description")
                if key in body
            )
            label = (
                f"Create Calendar event '{body['summary']}' on {args['calendar_id']} from {_calendar_time(body['start'])} to {_calendar_time(body['end'])}."
                + (f" Details: {detail}." if detail else "")
            )
        else:
            event_id = args.pop("event_id", None)
            calendar_id = args.get("calendar_id", "primary")
            current = get_event(
                services.calendar_token(action.user), event_id, calendar_id
            )
            body = validate_event(args, partial=True)
            # Check the full resulting boundaries, not just whichever field changed.
            validate_event(
                {
                    "summary": body.get("summary", current.get("summary", "Event")),
                    "start": body.get("start", current["start"]),
                    "end": body.get("end", current["end"]),
                }
            )
            if not current.get("etag"):
                raise ValueError(
                    "Calendar returned no event version. Refresh before updating."
                )
            args = {
                "event_id": event_id,
                "calendar_id": calendar_id,
                "expected_etag": current["etag"],
                "changes": body,
            }
            start, end = (
                body.get("start", current["start"]),
                body.get("end", current["end"]),
            )
            detail = "; ".join(
                f"{key}: {body[key]}"
                for key in ("summary", "location", "description")
                if key in body
            )
            label = (
                f"Update Calendar event '{current.get('summary', 'Event')}' on {calendar_id} to run from {_calendar_time(start)} to {_calendar_time(end)}."
                + (f" Changes: {detail}." if detail else "")
            )
    else:
        raise ValueError("Unsupported proposed action.")
    if (action.command.input_mode == "voice" and len(label) > 800) or (
        action.command.channel == "telegram" and len(label) > 1800
    ):
        raise ValueError(
            "This change is too long for a complete spoken/chat readback. Shorten it or enter it directly in the dashboard."
        )
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=action.user_id)
        m.Command.objects.select_for_update().get(pk=action.command_id)
        ensure_active(action.command)
        action.args, action.status = args, "awaiting_confirmation"
        action.save(update_fields=["args", "status"])
        proposal = m.ActionProposal.objects.create(
            user=action.user,
            action=action,
            readback=label,
            payload_digest=payload_digest({"tool": action.tool, "args": args}),
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        outcome = {
            "message": label + " Confirm to apply this change, or cancel.",
            "proposal": proposal_data(proposal),
        }
        action.result = outcome
        action.save(update_fields=["result"])
    return outcome


def decide(proposal, approve, revision, binding, persist_message=True):
    from . import services

    expired = False
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=proposal.user_id)
        proposal = m.ActionProposal.objects.select_for_update().get(pk=proposal.pk)
        action = m.ActionExecution.objects.select_for_update().get(
            pk=proposal.action_id
        )
        if (
            proposal.revision != revision
            or proposal.payload_digest != binding
            or binding != payload_digest({"tool": action.tool, "args": action.args})
        ):
            raise ValueError("The proposal changed. Review its current details.")
        if proposal.status in {"confirmed", "cancelled"}:
            return action.result or {
                "message": "This proposal was already resolved. Inspect its saved action in Command history.",
                "status": proposal.status,
            }
        if proposal.status != "pending":
            raise ValueError(
                "This proposal is no longer pending. Check its saved result before retrying."
            )
        if proposal.expires_at <= timezone.now():
            proposal.status = "expired"
            proposal.save(update_fields=["status"])
            action.status = "expired"
            action.result = {
                "message": "This confirmation expired. No change was made. Ask again for a fresh proposal.",
                "status": "expired",
            }
            expired = True
        else:
            if services.state(proposal.user).paused and approve:
                raise ValueError("Resume automations before confirming a change.")
            proposal.status = "executing" if approve else "cancelled"
            proposal.decided_at = timezone.now()
            proposal.save(update_fields=["status", "decided_at"])
            action.status = "running" if approve else "cancelled"
            action.result = (
                {"message": "Cancelled. No change was made.", "status": "cancelled"}
                if not approve
                else {}
            )
        action.save(update_fields=["status", "result"])
    if not approve or expired:
        record_decision(
            action, proposal, action.result, False, persist_message=persist_message
        )
        return action.result
    remote = action.tool.startswith("calendar_")
    try:
        # Remote I/O happens after a durable claim, outside database locks.
        remote_result = apply_calendar(action) if remote else None
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=action.user_id)
            action = m.ActionExecution.objects.select_for_update().get(pk=action.pk)
            args = action.args
            if action.tool == "schedule_task":
                task = services.create_task(action.user, args)
                result = {
                    "message": f"Scheduled '{task.name}' for {_schedule_label(task.schedule)}.",
                    "task_id": str(task.id),
                }
            elif action.tool in {"update_task", "set_task_enabled"}:
                task = m.ScheduledTask.objects.select_for_update().get(
                    user=action.user, pk=args["task_id"]
                )
                if payload_digest(_task_snapshot(task)) != args["expected"]:
                    raise ValueError(
                        "This task changed after the readback. Ask again to review the current version."
                    )
                if action.tool == "update_task":
                    clean = services.prepare_task(action.user, args["task"])
                    from .scheduling import next_due

                    task.name, task.payload, task.schedule = (
                        clean["name"],
                        clean["payload"],
                        clean["schedule"],
                    )
                    task.next_run_at = next_due(task.schedule) if task.enabled else None
                else:
                    from .scheduling import next_due

                    task.enabled = args["enabled"]
                    task.next_run_at = next_due(task.schedule) if task.enabled else None
                    if task.enabled and task.next_run_at is None:
                        raise ValueError(
                            "This task's scheduled time has passed. Choose a future time."
                        )
                task.save()
                if not task.enabled:
                    m.ScheduledOccurrence.objects.filter(
                        task=task, status="pending"
                    ).update(status="cancelled")
                elif action.tool == "update_task":
                    m.ScheduledOccurrence.objects.filter(
                        task=task, status="pending"
                    ).update(status="cancelled")
                result = {
                    "message": f"{'Updated' if action.tool == 'update_task' else 'Resumed' if task.enabled else 'Paused'} '{task.name}'.",
                    "task_id": str(task.id),
                }
            elif remote_result is not None:
                result = remote_result
            else:
                raise ValueError("Unsupported action.")
            action.status, action.result = "committed", result
            action.save(update_fields=["status", "result"])
            m.ActionProposal.objects.filter(pk=proposal.pk).update(status="confirmed")
    except Exception as exc:
        known = isinstance(
            exc, (ValueError, ConfigError, ProviderError, m.ScheduledTask.DoesNotExist)
        )
        uncertain = remote and not isinstance(exc, (ValueError, ConfigError))
        message = (
            "Calendar outcome could not be confirmed. Check Calendar and Activity before trying again."
            if uncertain
            else str(exc)[:1200]
            if known
            else "The action failed. Inspect Activity before trying again."
        )
        result = {
            "message": message,
            "status": "needs_attention" if uncertain else "failed",
        }
        m.ActionExecution.objects.filter(pk=action.pk).update(
            status=result["status"], result=result
        )
        m.ActionProposal.objects.filter(pk=proposal.pk).update(status=result["status"])
    record_decision(action, proposal, result, True, persist_message=persist_message)
    return result


def apply_calendar(action):
    from . import services
    from .integrations.calendar import create_event, update_event

    args = action.args
    if action.tool == "calendar_create_event":
        saved = create_event(services.calendar_token(action.user), args)
        message = f"Created Calendar event '{saved.get('summary', args['summary'])}' from {_calendar_time(args['start'])} to {_calendar_time(args['end'])}."
    elif action.tool == "calendar_update_event":
        saved = update_event(
            services.calendar_token(action.user),
            args["event_id"],
            {"calendar_id": args["calendar_id"], **args["changes"]},
            expected_etag=args["expected_etag"],
        )
        message = f"Updated Calendar event '{saved.get('summary', args['event_id'])}'."
    else:
        raise ValueError("Unsupported Calendar action.")
    return {"message": message, "event_id": saved["id"]}


def record_decision(action, proposal, result, approve, persist_message=True):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=action.user_id)
        origin = (
            m.Command.objects.select_for_update().filter(pk=action.command_id).first()
        )
        if not origin:
            return  # History may have been deleted after a non-executing decision.
        event(origin, "action_result", action_id=str(action.id), result=result)
        if origin.response:
            proposals = origin.response.get("action_proposals", [])
            final_state = m.ActionProposal.objects.get(pk=proposal.pk).status
            for item in proposals:
                if item["id"] == str(proposal.id):
                    item["status"] = final_state
            origin.response["action_proposals"] = proposals
            if origin.status != "cancelled":
                origin.status = (
                    "needs_attention"
                    if result.get("status") == "needs_attention"
                    else "completed"
                )
                origin.response["reply_text"] = result["message"]
            else:
                origin.response["reply_text"] = (
                    "Response stopped. Saved action result: " + result["message"]
                )
            origin.response["status"] = origin.status
            origin.save(update_fields=["response", "status"])
        if persist_message:
            m.Message.objects.create(
                conversation_id=origin.conversation_id,
                role="assistant",
                content=result["message"],
                metadata={
                    "action_result_id": str(action.id),
                    "action_status": result.get("status", "committed"),
                },
            )
        audit(
            action.user,
            "action.decided",
            action_id=str(action.id),
            approved=approve,
            status=result.get("status", "committed"),
        )


def execute_tool(command, step, name, args, gateway, response):
    from . import services
    from .capabilities import MUTATIONS, model_tools

    if not isinstance(name, str) or name not in {
        item["name"] for item in model_tools(command.user, command.model_profile)
    }:
        raise ValueError("This capability is unavailable or not permitted.")
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=command.user_id)
        m.Command.objects.select_for_update().get(pk=command.pk)
        ensure_active(command)
        action, created = m.ActionExecution.objects.get_or_create(
            user=command.user,
            command=command,
            step=step,
            defaults={"tool": name, "args": args},
        )
    if not created:
        return action.result
    if name in MUTATIONS:
        # Remote Calendar reads/refreshes happen before the short proposal-save
        # transaction, so slow network I/O cannot hold every SQLite writer.
        outcome = prepare(action)
        response["action_proposals"].append(outcome["proposal"])
        return outcome
    elif name == "search_web":
        found = gateway.grounded_search(
            args["query"], cancelled=cancellation_probe(command.id)
        )
        response["citations"].extend(found["sources"])
        if found.get("search_suggestions_html"):
            response["search_suggestions_html"].append(found["search_suggestions_html"])
        action.result = {"message": found["text"]}
    elif name == "list_tasks":
        rows = m.ScheduledTask.objects.filter(user=command.user).order_by(
            "next_run_at"
        )[:30]
        action.result = {
            "message": "\n".join(
                f"{task.name}: {'enabled' if task.enabled else 'paused'}; {_schedule_label(task.schedule)}. ID: {task.id}"
                for task in rows
            )
            or "You have no scheduled tasks."
        }
    elif name == "calendar_list_events":
        from .integrations.calendar import list_events

        saved = list_events(services.calendar_token(command.user))
        action.result = {
            "message": "\n".join(
                f"{item.get('summary', 'Event')}: {item.get('start', {})}. ID: {item['id']}"
                for item in saved.get("items", [])
            )
            or "No upcoming events were found."
        }
    else:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=command.user_id)
            m.Command.objects.select_for_update().get(pk=command.pk)
            ensure_active(command)
            if name == "draft_workflow":
                workflow = services.create_workflow(command.user, args)
                action.result = {
                    "message": "Workflow drafted. Review its sites, folders and actions in Automations before enabling it.",
                    "workflow_id": str(workflow.id),
                }
            elif name == "run_deep_research":
                from .contracts import ResearchArgs

                clean = ResearchArgs.model_validate(args)
                report = m.Report.objects.create(
                    user=command.user,
                    title=clean.topic[:240],
                    content=clean.model_dump(),
                )
                response["job_id"] = str(report.id)
                from .tasks import research_report

                transaction.on_commit(lambda: kick(research_report, str(report.id)))
                action.result = {
                    "message": "Research is queued. The PDF/DOCX will appear in Reports when complete.",
                    "report_id": str(report.id),
                }
            else:
                raise ValueError("Unregistered tool.")
            action.status = "committed"
            action.save(update_fields=["status", "result"])
    if name not in MUTATIONS:
        action.status = "committed"
    action.save(update_fields=["status", "result"])
    event(
        command,
        "tool_result",
        tool=name,
        action_id=str(action.id),
        status=action.status,
    )
    return action.result
