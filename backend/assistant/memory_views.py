from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import memory, models as m
from .capabilities import preferences
from .utils import audit


def serialize(row):
    return {"id": str(row.pk), "title": row.title, "content": row.content,
            "status": row.status, "pinned": row.pinned, "version": row.version,
            "source_message_id": row.source_message_id,
            "created_at": row.created_at, "updated_at": row.updated_at}


@api_view(["GET", "POST", "PATCH", "DELETE"])
def memories(request, pk=None):
    if pk:
        if request.method == "PATCH":
            return Response(serialize(memory.update(request.user, pk, request.data)))
        if request.method == "DELETE":
            memory.forget(request.user, pk, request.data.get("version"))
            return Response({"forgotten": True})
        return Response({"detail": "Use PATCH or DELETE for a memory."}, status=405)
    if request.method == "GET":
        pref = preferences(request.user)
        return Response({"enabled": pref.memory_enabled, "suggestions_enabled": pref.memory_suggestions,
            "limit_per_status": memory.LIMIT,
            "memories": [serialize(row) for row in m.PersonalMemory.objects.filter(user=request.user).order_by("-updated_at")[:400]]})
    if request.method == "POST":
        fact = memory.parse_fact(f"{request.data.get('title', '')}: {request.data.get('content', '')}", explicit=True)
        if not fact:
            raise ValueError("Use a short title/detail without credentials.")
        pinned = request.data.get("pinned", False)
        if type(pinned) is not bool:
            raise ValueError("pinned must be true or false.")
        fact["pinned"] = pinned
        with transaction.atomic():
            memory._lock(request.user)
            if not preferences(request.user).memory_enabled:
                raise ValueError("Enable shared memory before saving a detail.")
            row = memory.store(request.user, fact, status="active", explicit=True)
        return Response(serialize(row), status=201)
    if request.method == "PATCH":
        if not request.data or set(request.data) - {"enabled", "suggestions_enabled"}:
            raise ValueError("Choose enabled and/or suggestions_enabled.")
        with transaction.atomic():
            memory._lock(request.user)
            pref = preferences(request.user)
            for key, field in {"enabled": "memory_enabled", "suggestions_enabled": "memory_suggestions"}.items():
                if key in request.data:
                    if type(request.data[key]) is not bool:
                        raise ValueError("Memory settings require true or false.")
                    setattr(pref, field, request.data[key])
            pref.save(update_fields=["memory_enabled", "memory_suggestions"])
            audit(request.user, "memory.preferences", enabled=pref.memory_enabled, suggestions=pref.memory_suggestions)
        return Response({"enabled": pref.memory_enabled, "suggestions_enabled": pref.memory_suggestions})
    return Response({"detail": "Forget a specific memory by its ID."}, status=405)


@api_view(["POST"])
def scan_history(request):
    return Response({"suggestions_added": memory.import_previous(request.user), "scanned_up_to": 500})
