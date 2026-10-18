"""Google Calendar REST v3 and OAuth 2.0, restricted to owned event scope.

https://developers.google.com/workspace/calendar/api/auth
The application owns OAuth state validation and encrypted token storage. This
module never implements event deletion and rejects status=cancelled updates.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo

from .errors import ConfigError, ProviderError

SCOPE = "https://www.googleapis.com/auth/calendar.events.owned"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars"


class CalendarConflict(ValueError):
    """A conditional write was rejected before it changed the event."""


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    if not client_id or not redirect_uri:
        raise ConfigError("Configure GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI.")
    if not state or len(state) < 20:
        raise ValueError("OAuth state must be an unpredictable server-generated value.")
    parsed = urlsplit(redirect_uri)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        raise ConfigError("OAuth redirect URI must use HTTPS outside localhost.")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": SCOPE, "state": state, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "false"})


def _token_request(data):
    import httpx

    try:
        response = httpx.post(TOKEN_URL, data=data, timeout=20, follow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result.get("access_token"), str):
            raise ValueError
        # A broader pre-existing grant must not silently widen this connector.
        if result.get("scope") and set(result["scope"].split()) != {SCOPE}:
            raise ProviderError("Google returned an unexpected OAuth scope. Reconnect with owned event access only.")
        return result
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ProviderError("Google Calendar authorization failed. Reconnect the account.") from exc


def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    if not all((client_id, client_secret, redirect_uri, code)):
        raise ConfigError("Google OAuth credentials, redirect URI, and authorization code are required.")
    return _token_request({"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri,
                           "code": code, "grant_type": "authorization_code"})


def refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    if not all((client_id, client_secret, refresh_token)):
        raise ConfigError("Google OAuth credentials and refresh token are required.")
    return _token_request({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})


def _request(method, token, calendar_id="primary", event_id=None, **kwargs):
    import httpx

    if isinstance(token, dict):
        token = token.get("access_token")
    if not isinstance(token, str) or not token:
        raise ConfigError("Connect Google Calendar before using event tools.")
    if method not in {"GET", "POST", "PATCH"}:
        raise ValueError("Calendar deletion is not supported.")
    if not isinstance(calendar_id, str) or not calendar_id or len(calendar_id) > 300:
        raise ValueError("Invalid calendar ID.")
    url = f"{CALENDAR_URL}/{quote(calendar_id, safe='')}/events"
    if event_id:
        url += "/" + quote(event_id, safe="")
    try:
        extra_headers = kwargs.pop("headers", {})
        response = httpx.request(method, url, headers={"Authorization": f"Bearer {token}", **extra_headers}, timeout=20, follow_redirects=False, **kwargs)
        if response.status_code == 412:
            raise CalendarConflict("This event changed after the readback. Ask again to review the current version.")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, CalendarConflict):
            raise
        raise ProviderError("Google Calendar request failed. Check authorization and event details.") from exc


def list_events(token, time_min=None, time_max=None, calendar_id="primary", max_results=25, **kwargs):
    # Permit native Google names for callers using typed tool arguments.
    time_min = time_min or kwargs.get("timeMin") or datetime.now(timezone.utc).isoformat()
    time_max = time_max or kwargs.get("timeMax")
    params = {"timeMin": time_min, "maxResults": min(max(int(max_results), 1), 100), "singleEvents": "true", "orderBy": "startTime"}
    if time_max:
        params["timeMax"] = time_max
    return _request("GET", token, calendar_id, params=params)


def _event_time(value, zone):
    if isinstance(value, str):
        value = {"date": value} if len(value) == 10 else {"dateTime": value, "timeZone": zone}
    if not isinstance(value, dict) or set(value) - {"date", "dateTime", "timeZone"}:
        raise ValueError("Event time must contain date or dateTime and optional timeZone.")
    if bool(value.get("date")) == bool(value.get("dateTime")):
        raise ValueError("Use either date or dateTime for each event boundary.")
    if value.get("date"):
        date.fromisoformat(value["date"])
        return {"date": value["date"]}
    moment = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    zone = value.get("timeZone") or zone
    tz = ZoneInfo(zone)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    return {"dateTime": moment.isoformat(), "timeZone": zone}


def _event_body(args, partial=False):
    allowed = {"summary", "description", "location", "start", "end", "timezone", "timeZone", "calendar_id", "calendarId", "event_id", "id"}
    unknown = set(args) - allowed
    if unknown:
        raise ValueError("Unsupported calendar fields: " + ", ".join(sorted(unknown)))
    if not partial and (not args.get("summary") or not args.get("start") or not args.get("end")):
        raise ValueError("Calendar events require summary, start, and end.")
    body = {}
    for field, limit in {"summary": 300, "description": 8000, "location": 1000}.items():
        if field in args:
            if not isinstance(args[field], str) or len(args[field]) > limit:
                raise ValueError(f"Invalid calendar {field}.")
            body[field] = args[field]
    zone = args.get("timezone", args.get("timeZone", "Asia/Kolkata"))
    ZoneInfo(zone)
    for key in ("start", "end"):
        if key in args:
            body[key] = _event_time(args[key], zone)
    if "start" in body and "end" in body:
        key = "date" if "date" in body["start"] else "dateTime"
        if key not in body["end"]:
            raise ValueError("Start and end must use the same date format.")
        parser = date.fromisoformat if key == "date" else datetime.fromisoformat
        if parser(body["end"][key]) <= parser(body["start"][key]):
            raise ValueError("The event must end after it starts.")
    # Stable caller-generated IDs make retrying creation idempotent at Google.
    if "id" in args and not partial:
        import re
        if not isinstance(args["id"], str) or not re.fullmatch(r"[a-v0-9]{5,1024}", args["id"]):
            raise ValueError("Calendar event ID must use Google's base32hex alphabet.")
        body["id"] = args["id"]
    if not body:
        raise ValueError("No supported calendar fields to update.")
    return body


def validate_event(args, partial=False):
    return _event_body(args, partial=partial)


def get_event(token, event_id, calendar_id="primary"):
    if not isinstance(event_id, str) or not event_id or len(event_id) > 1024:
        raise ValueError("An exact event ID is required.")
    return _request("GET", token, calendar_id, event_id=event_id)


def create_event(token, args: dict):
    return _request("POST", token, args.get("calendar_id", args.get("calendarId", "primary")), json=_event_body(args), params={"sendUpdates": "none"})


def update_event(token, event_id: str, args: dict, expected_etag=None):
    if not isinstance(event_id, str) or not event_id or len(event_id) > 1024:
        raise ValueError("An event ID is required.")
    return _request("PATCH", token, args.get("calendar_id", args.get("calendarId", "primary")), event_id=event_id,
                    json=_event_body(args, partial=True), params={"sendUpdates": "none"}, headers={"If-Match": expected_etag} if expected_etag else {})
