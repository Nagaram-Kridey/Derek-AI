"""Conservative local routing for common spoken schedules; never executes them."""

import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone


def _clock(text):
    text = re.sub(r"\b([ap])\.\s*m\.?", r"\1m", text.casefold())
    match = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if match:
        hour, minute = int(match[1]), int(match[2] or 0)
        if not 1 <= hour <= 12 or minute > 59:
            return None
        return (hour % 12 + (12 if match[3] == "pm" else 0), minute, match.span())
    match = re.search(r"\bat\s+(\d{1,2}):(\d{2})\b", text)
    if match and int(match[1]) < 24 and int(match[2]) < 60:
        return int(match[1]), int(match[2]), match.span()
    return None


def _schedule(text):
    zone = settings.TIME_ZONE
    if re.search(r"\b\d{1,2}:\d{2}:\d{2}\b", text):
        return None
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b(?:next|starting|until|january|february|march|april|may|june|july|august|september|october|november|december)\b", text, re.I):
        return None
    normalized = re.sub(r"\b([ap])\.\s*m\.?", r"\1m", text.casefold())
    if len(re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\bat\s+\d{1,2}:\d{2}\b", normalized)) > 1:
        return None
    if re.search(r"\b(today|tomorrow|starting|from)\b", text, re.I) and re.search(r"\b(every\s*day|daily)\b", text, re.I):
        return None
    clock = _clock(text)
    daily = bool(re.search(r"\b(every\s*day|daily)\b", text, re.I))
    if re.search(r"\b(weekly|weekdays|weekends|monday|tuesday|wednesday|thursday|friday|saturday|sunday|except)\b", text, re.I):
        return None  # More complex schedules stay with the typed model tool.
    if daily:
        return {"kind": "daily", "time": f"{clock[0]:02}:{clock[1]:02}", "timezone": zone} if clock else None
    relative = re.search(r"\bin\s+(a|an|one|\d{1,4})\s+(minutes?|hours?)\b", text, re.I)
    if relative:
        if clock:
            return None
        number = 1 if relative[1].lower() in {"a", "an", "one"} else int(relative[1])
        if not 1 <= number <= 1440:
            return None
        delta = timedelta(minutes=number) if relative[2].lower().startswith("minute") else timedelta(hours=number)
        return {"kind": "once", "at": (timezone.now() + delta).isoformat(), "timezone": zone}
    # Do not reinterpret explicit dates, mixed timezones or an unspecified day.
    if clock and re.search(r"\b(today|tomorrow)\b", text, re.I):
        if re.search(r"\b(?:\d{4}-\d{2}-\d{2}|utc|gmt|pst|est|january|february|march|april|may|june|july|august|september|october|november|december)\b", text, re.I):
            return None
        now = timezone.localtime(timezone.now(), ZoneInfo(zone))
        date = now.date() + timedelta(days=1 if re.search(r"\btomorrow\b", text, re.I) else 0)
        at = datetime.combine(date, datetime.min.time(), ZoneInfo(zone)).replace(hour=clock[0], minute=clock[1])
        return {"kind": "once", "at": at.isoformat(), "timezone": zone}
    return None


def _reminder_message(text):
    # These forms anchor the subject in user text, not an assistant's prose.
    match = re.search(r"\bremind me\s+(?:to\s+|about\s+)?(.+)", text, re.I)
    if not match:
        match = re.search(r"\b(?:set|create|add|prepare)\s+(?:a\s+)?reminder\s+(?:to|about|for)\s+(.+)", text, re.I)
    if not match:
        return None
    body = match[1]
    # Time-first forms: 'remind me at 9pm today to drink water'.
    if re.match(r"(?:at\s+|today\b|tomorrow\b|daily\b|every\s*day\b|in\s+|\d)", body, re.I):
        subject = re.search(r"\b(?:to|about)\s+(.+)$", body, re.I)
        return subject[1].strip().rstrip(".!?") if subject else None
    body = re.split(r"\s+(?:at\s+\d|in\s+(?:a|an|one|\d)|today\b|tomorrow\b|every\s*day\b|daily\b)", body, maxsplit=1, flags=re.I)[0]
    return body.strip().rstrip(".!?") or None


def _previous_failed_subject(command):
    from . import models as m
    # Never reuse a committed task as a new create; that would duplicate it.
    previous = (m.Command.objects.filter(user=command.user, conversation_id=command.conversation_id,
                created_at__lt=command.created_at).order_by("-created_at").first())
    if not previous:
        return None
    action = (m.ActionExecution.objects.filter(user=command.user,
              command=previous,
              tool="schedule_task", status="failed").order_by("-created_at").first())
    if action and action.command.created_at >= timezone.now() - timedelta(minutes=15):
        if action.args.get("kind", "reminder") == "reminder":
            payload = action.args.get("payload", {})
            value = payload.get("message") if isinstance(payload, dict) else None
            if isinstance(value, str) and 1 <= len(value) <= 500:
                return value
    return None


def route(command):
    text = command.input_text.strip()
    if re.search(r"\b(not|don't|never|instead|example|hypothetically|and|then|also)\b", text, re.I):
        return None
    # Explicit different zones/dates require the model's full typed parser.
    if re.search(r"\b(?:utc|gmt|pst|est)\b|\b[A-Za-z_]+/[A-Za-z_]+\b", text, re.I):
        return None
    schedule = _schedule(text)
    if not schedule:
        return None
    prefix = r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?"
    website = re.search(prefix + r"(?:(?:create|add|set up)\s+(?:a\s+)?(?:new\s+)?(?:routine|automation|workflow)\s+to\s+)?open\b", text, re.I)
    if website:
        # Only an explicit HTTPS target or an unambiguous YouTube homepage.
        url_match = re.search(r"https://[^\s]+", text)
        if url_match:
            url = url_match[0].rstrip(".,!?")
        elif re.search(r"\byoutube\b", text, re.I) and not re.search(r"\b(channel|playlist|video|search|watch)\b", text, re.I):
            url = "https://www.youtube.com/"
        else:
            return None
        host = urlsplit(url).hostname
        return {"tool_calls": [{"name": "draft_workflow", "args": {
            "name": "Open " + (host or "website") + " routine", "description": text[:1000],
            "allowed_tools": ["browser.run"], "allowed_domains": [host], "allowed_paths": [],
            "steps": [{"tool": "browser.run", "args": {"actions": [{"type": "navigate", "url": url}]}}],
            "trigger": schedule}}]}
    if re.search(r"\b(update|change|move|reschedule|cancel|delete|pause|resume)\b", text, re.I):
        return None
    imperative = re.search(prefix + r"(?:remind me\b|(?:set|create|add|prepare)\s+(?:a\s+)?reminder\b)", text, re.I)
    message = _reminder_message(text) if imperative else None
    if not message and re.match(r"(?:please\s+)?set\s+(?:it|that)\b", text, re.I):
        message = _previous_failed_subject(command)
    if message and len(message) <= 500:
        return {"tool_calls": [{"name": "schedule_task", "args": {"name": message[:160],
            "kind": "reminder", "payload": {"message": message}, "schedule": schedule}}]}
    return None


def guard_unrecorded_claim(text, request=""):
    """A provider's completion claim is not evidence of a saved task."""
    first_person = re.search(r"\bi(?:['’]ve| have)?\s+(?:set|created|scheduled|enabled)\b", text, re.I)
    scheduling = re.search(r"\b(reminder|task|routine|workflow)\b", text, re.I)
    imperative = re.search(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:remind|set|create|add|schedule|prepare|open)\b", request, re.I)
    claimed = scheduling and (first_person or (imperative and re.search(r"\b(?:reminder|task|routine|workflow).{0,100}\b(?:set|created|scheduled|enabled)\b", text, re.I)))
    if claimed:
        return "No scheduling change was recorded. Tell me the reminder and its exact time, or the website and schedule. Reminders need an exact confirmation; browser routines need review in Automations."
    return text
