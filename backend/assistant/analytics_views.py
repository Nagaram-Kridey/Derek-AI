"""Admin analytics with distinct provider and end-to-end command timing."""
import math
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Min, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .models import Command
from .telemetry import model_label
from .telemetry_models import ModelObservation

SLOW_MS = 10000
SAMPLE_LIMIT = 10000


class IsWorkspaceAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))


def latency_summary(values):
    values = sorted(values)
    count = len(values)
    def percentile(fraction):
        return values[max(0, math.ceil(fraction * count) - 1)] if count else None
    return {"count": count, "mean": round(sum(values) / count, 1) if count else None,
            "p50": percentile(.5), "p95": percentile(.95), "max": values[-1] if count else None}


def counts(queryset):
    by_status = dict(queryset.values("status").annotate(total=Count("pk")).values_list("status", "total"))
    return {"requests": sum(by_status.values()), "succeeded": by_status.get("succeeded", 0),
            "failed": by_status.get("failed", 0), "cancelled": by_status.get("cancelled", 0),
            "slow": queryset.filter(latency_ms__gte=SLOW_MS).count()}


@api_view(["GET"])
@permission_classes([IsWorkspaceAdmin])
def analytics(request):
    try:
        days = int(request.query_params.get("days", "7"))
        if not 1 <= days <= 30:
            raise ValueError
    except (TypeError, ValueError):
        return Response({"detail": "Choose a whole number of days from 1 to 30."}, status=400)
    now = timezone.now()
    since = now - timedelta(days=days)
    observations = ModelObservation.objects.filter(created_at__gte=since, created_at__lte=now)
    samples = list(observations.order_by("-created_at").values("provider", "model_name", "latency_ms")[:SAMPLE_LIMIT])
    groups = defaultdict(list)
    for row in samples:
        groups[(row["provider"], row["model_name"])].append(row["latency_ms"])
    model_rows = []
    for provider, model in observations.order_by().values_list("provider", "model_name").distinct():
        group = observations.filter(provider=provider, model_name=model)
        model_rows.append({"provider": provider, "model": model_label(model), **counts(group),
                           "latency_ms": latency_summary(groups[(provider, model)])})
    commands = Command.objects.filter(created_at__gte=since, created_at__lte=now)
    command_status = dict(commands.values("status").annotate(total=Count("pk")).values_list("status", "total"))
    command_times = list(commands.order_by("-created_at").values("created_at", "started_at", "finished_at")[:SAMPLE_LIMIT])
    total_times = [round((row["finished_at"] - row["created_at"]).total_seconds() * 1000)
                   for row in command_times if row["finished_at"] and row["finished_at"] >= row["created_at"]]
    queue_times = [round((row["started_at"] - row["created_at"]).total_seconds() * 1000)
                   for row in command_times if row["started_at"] and row["started_at"] >= row["created_at"]]
    in_progress = commands.filter(status__in=["queued", "running"])
    issues = observations.filter(Q(status__in=["failed", "cancelled"]) | Q(latency_ms__gte=SLOW_MS)).order_by("-created_at")[:20]
    user_ids = set(commands.values_list("user_id", flat=True)) | set(observations.values_list("user_id", flat=True))
    provider_counts = counts(observations)
    from .image_models import ImageJob
    image_jobs = ImageJob.objects.filter(created_at__gte=since, created_at__lte=now)
    image_status = dict(image_jobs.values('status').annotate(total=Count('pk')).values_list('status','total'))
    image_times = list(image_jobs.order_by('-created_at').values('created_at','started_at','finished_at')[:SAMPLE_LIMIT])
    image_queue = [round((r['started_at']-r['created_at']).total_seconds()*1000) for r in image_times if r['started_at']]
    image_generation = [round((r['finished_at']-r['started_at']).total_seconds()*1000) for r in image_times if r['started_at'] and r['finished_at']]
    return Response({
        "images": {"requests":sum(image_status.values()),"by_status":image_status,"queue_ms":latency_summary(image_queue),"generation_ms":latency_summary(image_generation),"in_progress":image_status.get('queued',0)+image_status.get('running',0),"failures":image_status.get('failed',0)},
        "window": {"days": days, "since": since, "generated_at": now},
        "users": {"total": get_user_model().objects.filter(is_active=True).count(), "active": len(user_ids)},
        "provider": {**provider_counts, "slow_threshold_ms": SLOW_MS,
                     "latency_ms": latency_summary([row["latency_ms"] for row in samples]),
                     "collection_started_at": ModelObservation.objects.aggregate(at=Min("created_at"))["at"]},
        "models": sorted(model_rows, key=lambda row: (-row["requests"], row["provider"], row["model"])),
        "commands": {"requests": sum(command_status.values()), "by_status": command_status,
                     "end_to_end_ms": latency_summary(total_times), "queue_ms": latency_summary(queue_times),
                     "in_progress": in_progress.count(),
                     "stale": in_progress.filter(created_at__lt=now - timedelta(minutes=5)).count()},
        "recent_issues": [{"id": str(row.pk), "at": row.created_at, "provider": row.provider,
                           "model": model_label(row.model_name), "operation": row.operation,
                           "status": row.status, "error_code": row.error_code, "latency_ms": row.latency_ms}
                          for row in issues],
        "sampled": provider_counts["requests"] > SAMPLE_LIMIT or sum(command_status.values()) > SAMPLE_LIMIT,
        "notes": ["Models are grouped by requested model or router profile, not by the underlying served model.",
                  "Provider timing measures a budgeted gateway operation, including its internal retries; it is not time to first token.",
                  "Provider observations start after this update; historical command timestamps remain available separately.",
                  "Slow means at least 10 seconds. Stale means a queued or running command older than 5 minutes; it may still finish.",
                  "Latency percentiles use nearest rank and include failures/cancellations. Missing timing is null, not zero.",
                  "Timing summaries use the newest 10000 observations in this window; request counts include the entire window."],
    })
