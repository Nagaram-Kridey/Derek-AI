from django.urls import path
from assistant import views as v
from assistant import command_views as cv
from assistant import local_views as lv

urlpatterns = [path("", v.dashboard), path("health/", v.health)]
for suffix in ("", "/"):
    urlpatterns += [path(f"v1/auth/login{suffix}", v.login), path(f"v1/auth/logout{suffix}", v.logout), path(f"v1/turn{suffix}", v.turn)]
urlpatterns += [
    path("v1/capabilities/", cv.capabilities), path("v1/preferences/", cv.preferences),
    path("v1/local/voice/", lv.voice_window),
    path("v1/local/startup/", lv.startup),
    path("v1/commands/", cv.command_collection), path("v1/commands/<uuid:pk>/", cv.command_collection),
    path("v1/commands/cancel/", cv.cancel_command), path("v1/commands/by-request/<str:request_id>/", cv.command_by_request),
    path("v1/commands/<uuid:pk>/events/", cv.command_collection, {"events": True}),
    path("v1/action-proposals/<uuid:pk>/", cv.action_proposal),
    path("v1/action-proposals/<uuid:pk>/<str:action>/", cv.action_proposal),
    path("v1/conversations/", v.conversations), path("v1/conversations/<uuid:pk>/", v.conversations),
    path("v1/tasks/", v.scheduled_tasks), path("v1/tasks/<uuid:pk>/", v.scheduled_tasks), path("v1/tasks/<uuid:pk>/<str:action>/", v.scheduled_tasks),
    path("v1/workflows/", v.workflows), path("v1/workflows/<uuid:pk>/", v.workflows), path("v1/workflows/<uuid:pk>/<str:action>/", v.workflows),
    path("v1/runs/", v.runs), path("v1/runs/<uuid:pk>/cancel/", v.runs),
    path("v1/approvals/", v.approvals), path("v1/approvals/<uuid:pk>/<str:action>/", v.approvals),
    path("v1/reports/", v.reports), path("v1/reports/<uuid:pk>/download/", v.reports),
    path("v1/reports/<uuid:pk>/", v.reports),
    path("v1/reports/<uuid:pk>/detail/", v.reports, {"detail": True}),
    path("v1/reports/<uuid:pk>/cancel/", v.reports, {"action": "cancel"}),
    path("v1/reports/<uuid:pk>/deliver/", v.reports, {"action": "deliver"}),
    path("v1/notifications/<uuid:pk>/read/", v.notifications),
    path("v1/status/", v.status), path("v1/control/pause/", v.control), path("v1/audit/", v.activity), path("v1/notifications/", v.notifications),
    path("v1/devices/", v.devices), path("v1/devices/<uuid:pk>/", v.devices),
    path("v1/desktop/heartbeat/", v.heartbeat), path("v1/desktop/jobs/claim/", v.claim_job), path("v1/desktop/jobs/<uuid:pk>/complete/", v.complete_job),
    path("v1/calendar/connect/", v.calendar_connect), path("v1/calendar/callback/", v.calendar_callback), path("v1/calendar/events/", v.calendar_events),
    path("v1/export/", v.export_data), path("v1/history/", v.delete_history), path("v1/telegram/webhook/", v.telegram_webhook),
]
