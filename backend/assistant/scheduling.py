from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.conf import settings
import dateparser

def validate_schedule(value):
    if not isinstance(value, dict):
        raise ValueError("schedule must be an object")
    kind = value.get("kind")
    if kind not in {"once", "daily", "weekly"}:
        raise ValueError("Supported schedules: once, daily, weekly")
    if set(value) - {"kind", "at", "time", "weekdays", "timezone"}:
        raise ValueError("Unexpected schedule fields")
    zone = value.get("timezone", settings.TIME_ZONE)
    if not isinstance(zone, str) or not zone:
        raise ValueError("timezone must be a named timezone")
    try:
        ZoneInfo(zone)
    except (ValueError, KeyError) as exc:
        raise ValueError("Unknown timezone") from exc
    output = {"kind": kind, "timezone": zone}
    if kind == "once":
        dt = parse_time(value.get("at", ""), zone)
        output["at"] = dt.isoformat()
    else:
        try:
            t = time.fromisoformat(value.get("time", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("Provide an explicit time such as 09:00") from exc
        if t.tzinfo or t.second or t.microsecond:
            raise ValueError("Recurring times use HH:MM in the selected timezone")
        output["time"] = t.strftime("%H:%M")
        if kind == "weekly":
            days = value.get("weekdays", [])
            if not isinstance(days, list) or not days or any(type(day) is not int or not 0 <= day <= 6 for day in days):
                raise ValueError("weekdays must be 0=Monday through 6=Sunday")
            output["weekdays"] = sorted(set(days))
    return output

def parse_time(value, zone):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("An explicit time is required")
    dt = dateparser.parse(value, settings={"TIMEZONE": zone, "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future", "RELATIVE_BASE": timezone.now().astimezone(ZoneInfo(zone))})
    if dt is None:
        raise ValueError("Could not parse the time; provide an ISO datetime with timezone")
    return dt

def next_due(schedule, after=None):
    after = after or timezone.now()
    if schedule["kind"] == "once":
        at = datetime.fromisoformat(schedule["at"])
        return at if at > after else None
    zone = ZoneInfo(schedule["timezone"])
    local = after.astimezone(zone)
    t = time.fromisoformat(schedule["time"])
    for offset in range(8):
        date = local.date() + timedelta(days=offset)
        if schedule["kind"] == "weekly" and date.weekday() not in schedule["weekdays"]:
            continue
        candidate = datetime.combine(date, t, zone)
        # Normalize nonexistent DST wall times forward; use first occurrence in a fold.
        candidate = datetime.fromtimestamp(candidate.timestamp(), zone)
        if candidate > after:
            return candidate
    raise ValueError("Could not determine the next occurrence")
