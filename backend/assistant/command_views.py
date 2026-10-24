from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.decorators import throttle_classes
from . import commands, models as m
from .capabilities import catalog, preferences as owner_preferences, profile_details
from .utils import audit, kick


class CommandThrottle(UserRateThrottle):
    scope = "commands"

    def allow_request(self, request, view):
        return True if request.method == "GET" else super().allow_request(request, view)


@api_view(["POST"])
def cancel_command(request):
    return Response(
        commands.cancel_request(request.user, request.data.get("request_id"))
    )


@api_view(["GET"])
def command_by_request(request, request_id):
    row = get_object_or_404(
        m.Command, user=request.user, channel="web", request_id=request_id
    )
    return Response(commands.command_data(row))


@api_view(["GET"])
def capabilities(request):
    return Response(catalog(request.user))


@api_view(["GET", "PATCH"])
def preferences(request):
    row = owner_preferences(request.user)
    if request.method == "PATCH":
        if not request.data or set(request.data) - {"interactive_profile", "response_detail"}:
            raise ValueError("Choose interactive_profile and/or response_detail.")
        if "interactive_profile" in request.data and (not isinstance(request.data["interactive_profile"], str) or request.data["interactive_profile"] not in {"gemini", "configured"}):
            raise ValueError("Choose gemini or configured.")
        from .chat_policy import DETAILS
        if "response_detail" in request.data and (not isinstance(request.data["response_detail"], str) or request.data["response_detail"] not in DETAILS):
            raise ValueError("Choose auto, brief, balanced or detailed.")
        if "interactive_profile" in request.data:
            row.interactive_profile = request.data["interactive_profile"]
            row.save(update_fields=["interactive_profile"])
            audit(request.user, "preferences.updated", interactive_profile=row.interactive_profile)
        if "response_detail" in request.data:
            from .conversation_controls import set_detail
            set_detail(request.user, request.data["response_detail"])
            row.refresh_from_db()
    return Response(
        {
            "interactive_profile": row.interactive_profile,
            "response_detail": row.response_detail,
            "profiles": [
                profile_details(request.user, value)
                for value in ("gemini", "configured")
            ],
            "note": "Changes apply to new conversations. Existing conversations retain their model; no automatic provider fallback.",
        }
    )


@api_view(["GET", "POST"])
@throttle_classes([CommandThrottle])
def command_collection(request, pk=None, events=False):
    if pk:
        row = get_object_or_404(m.Command, user=request.user, pk=pk)
        if request.method != "GET":
            return Response(
                {
                    "detail": "Command records are read-only. Submit new commands to the collection."
                },
                status=405,
            )
        if events:
            try:
                after = max(0, int(request.query_params.get("after", "0")))
            except (TypeError, ValueError) as exc:
                raise ValueError("after must be an event ID.") from exc
            rows = list(
                row.events.filter(pk__gt=after)
                .order_by("pk")
                .values("id", "kind", "detail", "created_at")[:100]
            )
            return Response(
                {
                    "events": rows,
                    "next_event_id": rows[-1]["id"] if rows else after,
                    "status": row.status,
                }
            )
        return Response(
            {
                **commands.command_data(row),
                "actions": [
                    {
                        "id": str(action.id),
                        "tool": action.tool,
                        "status": action.status,
                        "result": action.result,
                    }
                    for action in row.actions.order_by("step")
                ],
                "proposals": [
                    commands.proposal_data(proposal)
                    for proposal in m.ActionProposal.objects.filter(action__command=row)
                ],
            }
        )
    if request.method == "GET":
        rows = m.Command.objects.filter(user=request.user)
        if request.query_params.get("conversation_id"):
            rows = rows.filter(conversation_id=request.query_params["conversation_id"])
        if request.query_params.get("active") == "true":
            rows = rows.filter(
                Q(status__in=["queued", "running", "needs_attention"])
                | Q(
                    status="awaiting_confirmation",
                    actions__proposal__status="pending",
                    actions__proposal__expires_at__gt=timezone.now(),
                )
            ).distinct()
        return Response(
            [commands.command_data(row) for row in rows.order_by("-created_at")[:100]]
        )
    row, created = commands.submit(
        request.user,
        request.data.get("text", ""),
        request_id=request.data.get("request_id"),
        conversation_id=request.data.get("conversation_id"),
        profile=request.data.get("model_profile"),
        input_mode=request.data.get("input_mode", "text"),
    )
    if row.status == "queued":
        from .tasks import process_command

        kick(process_command, str(row.id))
    return Response(
        commands.command_data(row),
        status=202 if row.status not in commands.FINAL else 200,
        headers={
            "Location": f"/v1/commands/{row.id}/",
            "X-Command-Replayed": "false" if created else "true",
        },
    )


@api_view(["GET", "POST"])
def action_proposal(request, pk, action=None):
    row = get_object_or_404(m.ActionProposal, user=request.user, pk=pk)
    if request.method == "GET":
        return Response(commands.proposal_data(row))
    if action not in {"confirm", "cancel"}:
        raise ValueError("Choose confirm or cancel.")
    revision, binding = request.data.get("revision"), request.data.get("payload_digest")
    if type(revision) is not int or not isinstance(binding, str):
        raise ValueError(
            "Include the proposal revision and payload_digest shown in the readback."
        )
    result = commands.decide(row, action == "confirm", revision, binding)
    row.refresh_from_db()
    return Response({**result, "proposal": commands.proposal_data(row)})
