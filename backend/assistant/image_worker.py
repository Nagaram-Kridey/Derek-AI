"""Single image service boundary. No provider retries or global interruption."""

import base64
import io
import json
import time
from pathlib import Path

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image

from .image_models import ImageJob
from .image_views import enabled
from .permissions import trial_admitted

BASE = "http://127.0.0.1:7860"
MAX_RESPONSE = 8 * 1024 * 1024


class ImageFailure(Exception):
    def __init__(self, code):
        self.code = code


def idle(client):
    try:
        response = client.get(
            BASE + "/sdapi/v1/progress",
            params={"skip_current_image": "true"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        return data["state"]["job_count"] == 0 and data.get("progress", 0) == 0
    except Exception:  # noqa: BLE001 -- fail closed without provider content in errors.
        return False


def router_generate(row):
    from .image_views import ROUTER_MODELS

    if row.checkpoint not in {r["id"] for r in ROUTER_MODELS}:
        raise ImageFailure("model_unavailable")
    try:
        with httpx.Client(
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(180, connect=5),
        ) as client:
            deadline = time.monotonic() + 180
            with client.stream(
                "POST",
                "http://127.0.0.1:3001/v1/images/generations",
                headers={"Authorization": "Bearer " + settings.FREELLMAPI_API_KEY},
                json={
                    "model": row.checkpoint,
                    "prompt": row.prompt,
                    "size": "1024x1024",
                    "n": 1,
                    "response_format": "b64_json",
                },
            ) as response:
                if response.status_code != 200:
                    codes = {
                        401: "configuration",
                        403: "configuration",
                        429: "provider_rate_limited",
                        400: "model_unavailable",
                    }
                    raise ImageFailure(
                        codes.get(response.status_code, "provider_error")
                    )
                body = bytearray()
                for block in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise ImageFailure("timeout")
                    body.extend(block)
                    if len(body) > MAX_RESPONSE:
                        raise ImageFailure("output_too_large")
            data = json.loads(body)
            if (
                data.get("model") != row.checkpoint
                or data.get("provider") != "cloudflare"
            ):
                raise ImageFailure("unexpected_provider")
            items = data.get("data")
            if (
                not isinstance(items, list)
                or len(items) != 1
                or not isinstance(items[0], dict)
                or not isinstance(items[0].get("b64_json"), str)
            ):
                raise ImageFailure("malformed_output")
            # Never fetch URL-only outputs; provider cannot redirect us to arbitrary hosts.
            raw = base64.b64decode(items[0]["b64_json"], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"} or image.size != (
                    1024,
                    1024,
                ):
                    raise ImageFailure("malformed_output")
                image.load()
                clean = io.BytesIO()
                image.convert("RGB").save(clean, format="PNG")
            return clean.getvalue()
    except ImageFailure:
        raise
    except httpx.TimeoutException:
        raise ImageFailure("timeout") from None
    except httpx.HTTPError:
        raise ImageFailure("service_unavailable") from None
    except Exception:  # noqa: BLE001 -- sanitized bounded provider decode failure.
        raise ImageFailure("malformed_output") from None


def generate(row):
    if getattr(settings, "TEST_IMAGE_PROVIDER", "a1111") == "freellmapi":
        return router_generate(row)
    if row.checkpoint != settings.TEST_IMAGE_CHECKPOINT:
        raise ImageFailure("checkpoint_changed")
    payload = {
        "prompt": row.prompt,
        "negative_prompt": row.negative_prompt,
        "seed": row.seed,
        "steps": 15,
        "width": 512,
        "height": 512,
        "batch_size": 1,
        "n_iter": 1,
        "sampler_name": "Euler",
        "save_images": False,
        "send_images": True,
        "override_settings": {
            "sd_model_checkpoint": getattr(settings, "TEST_IMAGE_CHECKPOINT_SHA256", "")
        },
        "override_settings_restore_afterwards": True,
    }
    try:
        with httpx.Client(
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(180, connect=5),
        ) as client:
            if not idle(client):
                raise ImageFailure("service_busy_or_unavailable")
            available = client.get(BASE + "/sdapi/v1/sd-models", timeout=5)
            available.raise_for_status()
            if len(available.content) > 2 * 1024 * 1024:
                raise ImageFailure("checkpoint_unavailable")
            if not any(
                isinstance(model, dict)
                and model.get("sha256") == settings.TEST_IMAGE_CHECKPOINT_SHA256
                for model in available.json()
            ):
                raise ImageFailure("checkpoint_unavailable")
            deadline = time.monotonic() + 180
            with client.stream(
                "POST", BASE + "/sdapi/v1/txt2img", json=payload
            ) as response:
                if response.status_code != 200:
                    raise ImageFailure("provider_error")
                body = bytearray()
                for block in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise ImageFailure("timeout")
                    body.extend(block)
                    if len(body) > MAX_RESPONSE:
                        raise ImageFailure("output_too_large")
            data = json.loads(body)
            images = data.get("images")
            if (
                not isinstance(images, list)
                or len(images) != 1
                or not isinstance(images[0], str)
            ):
                raise ImageFailure("malformed_output")
            raw = base64.b64decode(images[0], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "PNG" or image.size != (512, 512):
                    raise ImageFailure("malformed_output")
                image.load()
                clean = io.BytesIO()
                image.convert("RGB").save(clean, format="PNG")
            return clean.getvalue()
    except ImageFailure:
        raise
    except httpx.TimeoutException:
        raise ImageFailure("timeout") from None
    except httpx.HTTPError:
        raise ImageFailure("service_unavailable") from None
    except Exception:  # noqa: BLE001 -- fail closed without provider content in errors.
        raise ImageFailure("malformed_output") from None


def recover_interrupted():
    # Called once by the dedicated worker after acquiring its process lock.
    from companion.journal import WorkerLock

    lock_path = Path(settings.MEDIA_ROOT).parent / "runtime" / "image-worker.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with WorkerLock(lock_path):
            ImageJob.objects.filter(status="running").update(
                status="failed",
                error_code="interrupted_unknown_outcome",
                finished_at=timezone.now(),
            )
    except RuntimeError:
        return False
    return True


def run_once():
    if not enabled():
        return False
    # Existing WorkerLock owns an advisory OS lock; independent startup cannot
    # overlap a live generator. Keep lock held throughout provider I/O.
    from companion.journal import WorkerLock

    lock_path = Path(settings.MEDIA_ROOT).parent / "runtime" / "image-worker.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with WorkerLock(lock_path):
            return _run_locked()
    except RuntimeError:
        return False


def _run_locked():
    with transaction.atomic():
        if ImageJob.objects.filter(status="running").exists():
            return False
        row = (
            ImageJob.objects.select_for_update()
            .filter(status="queued")
            .order_by("created_at")
            .first()
        )
        if not row:
            return False
        if not row.user.is_active or not trial_admitted(row.user):
            row.status = "cancelled"
            row.error_code = "account_unavailable"
            row.finished_at = timezone.now()
            row.save()
            return True
        row.status = "running"
        row.started_at = timezone.now()
        row.save(update_fields=["status", "started_at"])
    try:
        output = generate(row)
        row.output.save(str(row.pk) + ".png", ContentFile(output), save=False)
        row.status = "completed"
    except ImageFailure as exc:
        row.status = "failed"
        row.error_code = exc.code
    except Exception:  # noqa: BLE001 -- fail closed without provider content in errors.
        row.status = "failed"
        row.error_code = "storage_error"
    row.finished_at = timezone.now()
    row.save(update_fields=["output", "status", "error_code", "finished_at"])
    return True
