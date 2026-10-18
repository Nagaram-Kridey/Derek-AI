"""Authenticated, narrowly typed controls for the managed local app."""

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import audit


@api_view(["POST"])
def voice_window(request):
    if not settings.LOCAL_EXECUTION:
        return Response(
            {
                "detail": "The native voice window is available through the managed local app."
            },
            status=409,
        )
    mode = request.data.get("mode", "online")
    if mode not in {"online", "private"}:
        raise ValueError("Choose online or private voice.")
    from desktop.supervisor import send_control

    if not send_control("private-voice" if mode == "private" else "voice"):
        return Response(
            {
                "detail": "The local voice window could not open. Close any voice window in the other mode, then try again from the Windows tray."
            },
            status=409,
        )
    audit(request.user, "voice.window_opened", mode=mode)
    return Response({"opened": True, "microphone": "closed_until_listen", "mode": mode})


@api_view(["POST"])
def startup(request):
    if not settings.LOCAL_EXECUTION:
        return Response(
            {"detail": "Startup controls belong to the managed local Windows app."},
            status=409,
        )
    enabled = request.data.get("enabled")
    if type(enabled) is not bool:
        raise ValueError("enabled must be true or false.")
    from desktop.supervisor import send_control

    if not send_control("autostart-on" if enabled else "autostart-off"):
        return Response(
            {
                "detail": "The local launcher could not update startup. Use its tray menu or restart it."
            },
            status=409,
        )
    audit(request.user, "local.startup_updated", enabled=enabled)
    return Response({"enabled": enabled})
