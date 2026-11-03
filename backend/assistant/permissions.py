"""Identity and a narrow tester access boundary, enforced before API handlers."""
from django.conf import settings
from rest_framework.permissions import BasePermission


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))


def can_use_tools(user):
    return is_admin(user) and not getattr(settings, "TEST_WORKSPACE", False)


def can_research(user):
    return can_use_tools(user) or (getattr(settings, "TEST_WORKSPACE", False) and user.is_active and trial_admitted(user))


def can_use_browser_voice(user):
    return can_research(user)


def trial_admitted(user):
    if not getattr(settings, "TEST_WORKSPACE", False):
        return True
    if is_admin(user) and not hasattr(user, "google_identity"):
        return True
    identity = getattr(user, "google_identity", None)
    if getattr(settings, "TEST_OPEN_SIGNUP", False):
        return bool(identity and user.is_active)
    invited = {email.strip().casefold() for email in getattr(settings, "TEST_INVITED_EMAILS", [])}
    return bool(identity and identity.email.casefold() in invited)


class WorkspaceAccess(BasePermission):
    message = "This control is available to the workspace administrator only."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not trial_admitted(request.user):
            return False
        if getattr(settings, "TEST_WORKSPACE", False):
            path = request.path.rstrip("/")
            if path in {"/v1/auth/me", "/v1/auth/logout", "/v1/turn", "/v1/status"}:
                return True
            if path.startswith("/v1/telegram/"):
                return True
            if path in {"/v1/preferences", "/v1/notifications"} or path.startswith("/v1/memories"):
                return True
            if path.startswith("/v1/reports"):
                return not path.endswith("/deliver")
            if path.startswith(("/v1/tasks", "/v1/audit")):
                return request.method in {"GET", "HEAD", "OPTIONS"}
            if path.startswith("/v1/conversations"):
                return True
            return path.startswith("/v1/commands") and not path.endswith("/telegram")
        if is_admin(request.user):
            return True
        path = request.path.rstrip("/")
        # Testers may use their own chat/history, personal preferences/memories,
        # read-only schedule/reports and in-app notifications. Host controls and
        # every tool/action endpoint are owner-only until separately enabled.
        if path in {"/v1/auth/me", "/v1/auth/logout", "/v1/turn", "/v1/status", "/v1/preferences"}:
            return True
        if path.startswith(("/v1/conversations", "/v1/memories")):
            return True
        if path.startswith("/v1/commands"):
            return not path.endswith("/telegram")
        if path.startswith("/v1/notifications"):
            return True
        if path.startswith(("/v1/tasks", "/v1/reports", "/v1/audit", "/v1/capabilities")):
            return request.method in {"GET", "HEAD", "OPTIONS"}
        return False
