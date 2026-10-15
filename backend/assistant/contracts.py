"""Workflow definitions are data. All executable actions have typed contracts."""
from typing import Literal
from urllib.parse import urlsplit
from pathlib import PureWindowsPath
import ipaddress
from pydantic import BaseModel, ConfigDict, Field, model_validator

RISKS = {"purchase", "payment", "account_security", "permanent_delete"}
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class PathArg(Strict):
    path: str = Field(min_length=1, max_length=4096)
class WriteArg(PathArg):
    content: str = Field(max_length=1_000_000)
    overwrite: bool = False
class MoveArg(Strict):
    source: str
    destination: str
class BrowserAction(Strict):
    type: Literal["navigate", "read", "fill", "click", "select"]
    url: str | None = None
    selector: str | None = None
    value: str | None = None
    expected_url: str | None = None
    expected_text: str | None = None
    risk: Literal["normal", "purchase", "payment", "account_security", "permanent_delete"] = "normal"
    @model_validator(mode="after")
    def valid_action(self):
        if self.type == "navigate" and not self.url:
            raise ValueError("navigate requires url")
        if self.type != "navigate" and not self.selector:
            raise ValueError("DOM actions require a unique selector")
        if self.type in {"fill", "select", "click"} and (not self.expected_url or not self.expected_text):
            raise ValueError("Mutating actions require expected_url and expected_text")
        if self.type in {"fill", "select"} and self.value is None:
            raise ValueError("fill/select require value")
        return self
class BrowserArgs(Strict):
    actions: list[BrowserAction] = Field(min_length=1, max_length=30)
class ResearchArgs(Strict):
    topic: str = Field(min_length=3, max_length=2000)
    include_academic: bool = False
    report_kind: Literal["standard", "project_ideas"] = "standard"
class NotifyArgs(Strict):
    message: str = Field(min_length=1, max_length=4000)
class CalendarCreate(Strict):
    summary: str = Field(min_length=1, max_length=240)
    start: dict
    end: dict
    description: str = Field(default="", max_length=10000)
    location: str = Field(default="", max_length=500)
    @model_validator(mode="after")
    def valid_times(self):
        from datetime import datetime, date
        kind = "dateTime" if "dateTime" in self.start else "date"
        if kind not in self.start or kind not in self.end:
            raise ValueError("start/end must both contain date or dateTime")
        parse = datetime.fromisoformat if kind == "dateTime" else date.fromisoformat
        if not isinstance(self.start[kind], str) or not isinstance(self.end[kind], str):
            raise ValueError("Calendar times must be ISO strings")
        start, end = parse(self.start[kind]), parse(self.end[kind])
        if kind == "dateTime" and (start.tzinfo is None or end.tzinfo is None):
            raise ValueError("Calendar dateTime values must include a timezone offset")
        if end <= start:
            raise ValueError("Calendar end must be after start")
        if set(self.start) - {kind, "timeZone"} or set(self.end) - {kind, "timeZone"}:
            raise ValueError("Unexpected calendar time fields")
        return self
class CalendarUpdate(CalendarCreate):
    event_id: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_@.-]+$")

SCHEMAS = {
    "file.list": PathArg, "file.read": PathArg, "file.write": WriteArg,
    "file.move": MoveArg, "file.delete": PathArg, "browser.run": BrowserArgs,
    "research.run": ResearchArgs, "notify": NotifyArgs,
    "calendar.create": CalendarCreate, "calendar.update": CalendarUpdate,
}
DESKTOP_TOOLS = {name for name in SCHEMAS if name.startswith(("file.", "browser."))}

def normalize_domain(value):
    if not isinstance(value, str):
        raise ValueError("Domain must be text")
    host = value.strip().lower().rstrip(".")
    if any(c in host for c in "/:*@ \\") or "." not in host:
        raise ValueError("Use exact public domain names without wildcards, ports, or URLs")
    host = host.encode("idna").decode("ascii")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literals are not allowed browser targets")
    if host.endswith((".local", ".localhost", ".internal", ".test", ".invalid")):
        raise ValueError("Private browser targets are not allowed")
    return host

def validate_workflow(data):
    from .scheduling import validate_schedule
    allowed = data.get("allowed_tools", [])
    if not isinstance(allowed, list) or len(allowed) > 16 or any(not isinstance(t, str) or t not in SCHEMAS for t in allowed):
        raise ValueError("allowed_tools must contain registered tool names")
    domains = data.get("allowed_domains", [])
    if not isinstance(domains, list) or len(domains) > 64:
        raise ValueError("allowed_domains must be a list of at most 64 exact domains")
    domains = [normalize_domain(d) for d in domains]
    paths = data.get("allowed_paths", [])
    if not isinstance(paths, list) or len(paths) > 16:
        raise ValueError("allowed_paths must be a list")
    for path in paths:
        if not isinstance(path, str):
            raise ValueError("Approved folders must be text")
        p = PureWindowsPath(path)
        if not p.is_absolute() or str(p) == p.anchor or ".." in p.parts or path.startswith("\\\\"):
            raise ValueError("Approved folders must be absolute local Windows subfolders, never a drive root or network share")
    steps = data.get("steps", [])
    if not isinstance(steps, list) or not 1 <= len(steps) <= 30:
        raise ValueError("A workflow needs 1–30 steps")
    cleaned = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"tool", "args"} or step["tool"] not in allowed:
            raise ValueError("Each step must have tool/args and its tool must be explicitly allowed")
        tool = step["tool"]
        args = SCHEMAS[tool].model_validate(step["args"]).model_dump(exclude_none=True)
        if tool.startswith("file."):
            if not paths:
                raise ValueError("File workflows require allowed_paths")
            for key in ("path", "source", "destination"):
                if key in args and not any(PureWindowsPath(args[key]).is_relative_to(PureWindowsPath(p)) for p in paths):
                    raise ValueError("File action is outside approved folders")
                if key in args and ".." in PureWindowsPath(args[key]).parts:
                    raise ValueError("Path traversal is not permitted")
        if tool == "browser.run":
            if not domains:
                raise ValueError("Browser workflows require allowed_domains")
            for action in args["actions"]:
                for key in ("url", "expected_url"):
                    if key in action:
                        u = urlsplit(action[key])
                        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or normalize_domain(u.hostname or "") not in domains:
                            raise ValueError("Browser URL is outside the approved HTTPS domains")
        cleaned.append({"tool": tool, "args": args})
    trigger = data.get("trigger", {"kind": "manual"})
    if not isinstance(trigger, dict):
        raise ValueError("trigger must be an object")
    if trigger.get("kind") != "manual":
        trigger = validate_schedule(trigger)
    return {"steps": cleaned, "allowed_tools": sorted(set(allowed)), "allowed_domains": domains, "allowed_paths": paths, "trigger": trigger}

def step_risk(step):
    if step["tool"] == "file.delete":
        return "permanent_delete"
    if step["tool"] == "browser.run":
        return next((a["risk"] for a in step["args"]["actions"] if a.get("risk", "normal") in RISKS), None)
    return None
