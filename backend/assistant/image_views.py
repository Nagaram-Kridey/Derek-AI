"""Authenticated private image API. Fixed generation profile, no client provider options."""

import hashlib
import json
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .image_models import ImageJob
from .models import Conversation
from .permissions import trial_admitted


class ImageAccess(BasePermission):
    def has_permission(self, request, view):
        return bool(
            getattr(settings, "TEST_WORKSPACE", False)
            and request.user.is_authenticated
            and request.user.is_active
            and trial_admitted(request.user)
        )


ROUTER_MODELS = [
    {"id": "@cf/bytedance/stable-diffusion-xl-lightning", "label": "SDXL Lightning"},
    {"id": "@cf/stabilityai/stable-diffusion-xl-base-1.0", "label": "SDXL Base 1.0"},
]


def provider():
    return getattr(settings, "TEST_IMAGE_PROVIDER", "a1111")


def enabled():
    if not getattr(settings, "TEST_WORKSPACE", False) or not getattr(
        settings, "TEST_IMAGE_ENABLED", False
    ):
        return False
    if provider() == "freellmapi":
        return bool(settings.FREELLMAPI_API_KEY)
    return bool(
        getattr(settings, "TEST_IMAGE_CHECKPOINT", "")
        and re.fullmatch(
            r"[a-fA-F0-9]{64}", getattr(settings, "TEST_IMAGE_CHECKPOINT_SHA256", "")
        )
    )


def serialize(row):
    ready = row.status == "completed" and bool(row.output)
    base = "/v1/images/" + str(row.pk)
    return {
        "id": str(row.pk),
        "model": row.checkpoint,
        "provider": "freellmapi" if row.checkpoint.startswith("@cf/") else "a1111",
        "prompt": row.prompt,
        "negative_prompt": row.negative_prompt,
        "seed": row.seed,
        "status": row.status,
        "error_code": row.error_code,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "preview_url": base + "/preview/" if ready else None,
        "download_url": base + "/download/" if ready else None,
    }


@api_view(["GET", "POST", "DELETE"])
@permission_classes([ImageAccess])
def images(request, pk=None, action=None):
    if pk:
        row = get_object_or_404(ImageJob, user=request.user, pk=pk, deleted=False)
        if action in {"preview", "download"} and request.method == "GET":
            if row.status != "completed" or not row.output:
                return Response({"detail": "Image is not ready."}, status=409)
            return FileResponse(
                row.output.open("rb"),
                content_type="image/png",
                as_attachment=action == "download",
                filename="Derek-" + str(row.pk) + ".png",
            )
        if action == "cancel" and request.method == "POST":
            with transaction.atomic():
                row = ImageJob.objects.select_for_update().get(pk=row.pk)
                if row.status != "queued":
                    return Response(
                        {"detail": "Only queued images can be cancelled."}, status=409
                    )
                row.status = "cancelled"
                row.finished_at = timezone.now()
                row.save(update_fields=["status", "finished_at"])
            return Response(serialize(row))
        if action:
            return Response(status=405)
        if request.method == "DELETE":
            with transaction.atomic():
                row = ImageJob.objects.select_for_update().get(pk=row.pk)
                if row.status in {"queued", "running"}:
                    return Response(
                        {
                            "detail": "Cancel queued work or wait for running work before deleting."
                        },
                        status=409,
                    )
                row.output.delete(save=False)
                row.deleted = True
                row.prompt = ""
                row.negative_prompt = ""
                row.save(
                    update_fields=["output", "deleted", "prompt", "negative_prompt"]
                )
            return Response(status=204)
        if request.method == "GET":
            return Response(serialize(row))
        return Response(status=405)
    if request.method == "GET":
        return Response(
            {
                "enabled": enabled(),
                "provider": provider(),
                "models": ROUTER_MODELS if provider() == "freellmapi" else [],
                "default_model": getattr(
                    settings, "TEST_IMAGE_MODEL", ROUTER_MODELS[0]["id"]
                )
                if provider() == "freellmapi"
                else None,
                "disabled_reason": ""
                if enabled()
                else "Local image generation is disabled until the hardware benchmark passes.",
                "jobs": [
                    serialize(r)
                    for r in ImageJob.objects.filter(user=request.user, deleted=False)[
                        :100
                    ]
                ],
            }
        )
    if request.method != "POST":
        return Response(status=405)
    raw = request.data
    if not isinstance(raw, dict) or set(raw) - {
        "prompt",
        "negative_prompt",
        "seed",
        "request_id",
        "conversation_id",
        "create_conversation",
        "model",
    }:
        raise ValueError("Unsupported image generation parameters.")
    prompt, negative, key = (
        raw.get("prompt"),
        raw.get("negative_prompt", ""),
        raw.get("request_id"),
    )
    seed = raw.get("seed", -1)
    if (
        not isinstance(prompt, str)
        or not prompt.strip()
        or len(prompt) > 2000
        or not isinstance(negative, str)
        or len(negative) > 1000
    ):
        raise ValueError(
            "Use a prompt up to 2000 characters and negative prompt up to 1000."
        )
    if "<" in prompt + negative or ">" in prompt + negative:
        raise ValueError("Extension tags are not supported.")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key):
        raise ValueError("A valid request_id is required.")
    if type(seed) != int or not -1 <= seed <= 4294967295:
        raise ValueError("Seed must be -1 or an unsigned 32-bit integer.")
    model = (
        raw.get("model", getattr(settings, "TEST_IMAGE_MODEL", ROUTER_MODELS[0]["id"]))
        if provider() == "freellmapi"
        else getattr(settings, "TEST_IMAGE_CHECKPOINT", "")
    )
    if provider() == "freellmapi":
        if model not in {r["id"] for r in ROUTER_MODELS}:
            raise ValueError("Choose an available image model.")
        if negative or seed != -1:
            raise ValueError(
                "This image provider does not support negative prompts or seeds."
            )
    elif "model" in raw:
        raise ValueError("The local checkpoint is administrator configured.")
    create_conversation = raw.get("create_conversation", False)
    if type(create_conversation) != bool:
        raise ValueError("create_conversation must be boolean.")
    conv = raw.get("conversation_id") or None
    if create_conversation and conv:
        raise ValueError("Use an existing conversation or create a new one.")
    if conv:
        get_object_or_404(Conversation, user=request.user, pk=conv)
    fingerprint = hashlib.sha256(
        json.dumps(
            [prompt.strip(), negative, seed, conv, create_conversation, model]
        ).encode()
    ).hexdigest()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        previous = ImageJob.objects.filter(user=request.user, request_id=key).first()
        if previous:
            if previous.fingerprint != fingerprint:
                return Response(
                    {"detail": "Request ID belongs to different image settings."},
                    status=409,
                )
            return Response(serialize(previous), status=200)
        if not enabled():
            return Response(
                {"detail": "Image generation is not configured or enabled."},
                status=503,
            )
        if ImageJob.objects.filter(
            user=request.user, status__in=["queued", "running"]
        ).exists():
            return Response({"detail": "Wait for your unfinished image."}, status=409)
        if ImageJob.objects.filter(status__in=["queued", "running"]).count() >= 10:
            return Response({"detail": "Image queue is full."}, status=429)
        day = timezone.localdate(timezone=ZoneInfo("Asia/Kolkata"))
        start = timezone.make_aware(
            datetime.combine(day, time()), ZoneInfo("Asia/Kolkata")
        )
        if (
            ImageJob.objects.filter(
                user=request.user,
                created_at__gte=start,
                created_at__lt=start + timedelta(days=1),
            ).count()
            >= 5
        ):
            return Response({"detail": "Daily image allowance reached."}, status=429)
        if create_conversation:
            conv = Conversation.objects.create(
                user=request.user,
                title=prompt.strip()[:160],
                model_profile="configured",
            ).pk
        row = ImageJob.objects.create(
            user=request.user,
            conversation_id=conv,
            request_id=key,
            fingerprint=fingerprint,
            prompt=prompt.strip(),
            negative_prompt=negative,
            seed=seed,
            checkpoint=model,
        )
    return Response(serialize(row), status=202)
