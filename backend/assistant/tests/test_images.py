import base64
import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image

from assistant import image_worker
from assistant.image_models import ImageJob

pytestmark = pytest.mark.django_db


@pytest.fixture
def image_mode(settings):
    settings.TEST_WORKSPACE = True
    settings.TEST_IMAGE_ENABLED = True
    settings.TEST_IMAGE_CHECKPOINT = "test.safetensors"
    settings.TEST_IMAGE_CHECKPOINT_SHA256 = "a" * 64
    return settings


def create(client, **kw):
    return client.post(
        "/v1/images/", {"prompt": "A flower", "request_id": "one", **kw}, format="json"
    )


def test_disabled_and_strict_input(client, image_mode):
    image_mode.TEST_IMAGE_ENABLED = False
    assert create(client).status_code == 503
    image_mode.TEST_IMAGE_ENABLED = True
    for extra in [
        {"url": "http://evil"},
        {"prompt": "<lora:bad:1>"},
        {"seed": True},
        {"steps": 100},
    ]:
        assert create(client, **extra).status_code == 400
    assert not ImageJob.objects.exists()


def test_replay_cancel_delete_preserves_quota(client, user, image_mode):
    first = create(client, create_conversation=True)
    assert first.status_code == 202
    assert first.data["conversation_id"]
    assert create(client, create_conversation=True).data["id"] == first.data["id"]
    assert create(client, prompt="changed").status_code == 409
    assert create(client, request_id="two").status_code == 409
    pk = first.data["id"]
    assert client.post("/v1/images/" + pk + "/cancel/").status_code == 200
    assert client.delete("/v1/images/" + pk + "/").status_code == 204
    assert create(client, create_conversation=True).status_code == 200
    for i in range(4):
        response = create(client, request_id="new" + str(i))
        assert response.status_code == 202
        client.post("/v1/images/" + response.data["id"] + "/cancel/")
    assert create(client, request_id="six").status_code == 429
    assert ImageJob.objects.filter(user=user).count() == 5


def test_ownership_and_download(client, user, image_mode):
    other = get_user_model().objects.create_user("other")
    row = ImageJob.objects.create(
        user=other,
        request_id="x",
        fingerprint="x",
        prompt="private",
        checkpoint="x",
        status="completed",
    )
    row.output.save("test.png", ContentFile(b"private"), save=True)
    for suffix in ["", "preview/", "download/"]:
        assert client.get("/v1/images/" + str(row.pk) + "/" + suffix).status_code == 404
    assert client.delete("/v1/images/" + str(row.pk) + "/").status_code == 404


def test_queue_capacity(client, user, image_mode):
    for i in range(10):
        other = get_user_model().objects.create_user("u" + str(i))
        ImageJob.objects.create(
            user=other, request_id="x", fingerprint="x", prompt="x", checkpoint="x"
        )
    assert create(client).status_code == 429


def test_worker_outcomes_and_recovery(client, user, image_mode):
    first = create(client).data["id"]
    with patch("assistant.image_worker.generate", return_value=b"png"):
        assert image_worker.run_once()
    row = ImageJob.objects.get(pk=first)
    assert row.status == "completed" and row.output
    assert client.get("/v1/images/" + first + "/download/").status_code == 200
    create(client, request_id="two")
    with patch(
        "assistant.image_worker.generate",
        side_effect=image_worker.ImageFailure("timeout"),
    ):
        assert image_worker.run_once()
    assert ImageJob.objects.get(request_id="two").error_code == "timeout"
    row = ImageJob.objects.create(
        user=user,
        request_id="three",
        fingerprint="x",
        prompt="x",
        checkpoint="x",
        status="running",
    )
    assert image_worker.recover_interrupted()
    row.refresh_from_db()
    assert row.status == "failed" and row.error_code == "interrupted_unknown_outcome"


def test_provider_bounds_and_png_validation(user, image_mode):
    import httpx

    row = ImageJob(user=user, prompt="x", checkpoint="test.safetensors", seed=-1)

    def handler(request):
        if request.url.path.endswith("sd-models"):
            return httpx.Response(200, json=[{"sha256": "a" * 64}])
        if request.url.path.endswith("progress"):
            return httpx.Response(200, json={"state": {"job_count": 0}, "progress": 0})
        return httpx.Response(200, json={"images": [base64.b64encode(b"bad").decode()]})

    real = httpx.Client
    with (
        patch(
            "assistant.image_worker.httpx.Client",
            side_effect=lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
        ),
        pytest.raises(image_worker.ImageFailure) as error,
    ):
        image_worker.generate(row)
    assert error.value.code == "malformed_output"


def test_valid_png_busy_and_network_failure(user, image_mode):
    import httpx

    row = ImageJob(user=user, prompt="x", checkpoint="test.safetensors", seed=-1)
    output = io.BytesIO()
    Image.new("RGB", (512, 512), "white").save(output, format="PNG")
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("sd-models"):
            return httpx.Response(200, json=[{"sha256": "a" * 64}])
        if request.url.path.endswith("progress"):
            return httpx.Response(200, json={"state": {"job_count": 0}, "progress": 0})
        import json

        body = json.loads(request.content)
        assert body["width"] == 512 and body["steps"] == 15 and body["batch_size"] == 1
        assert body["override_settings"]["sd_model_checkpoint"] == "a" * 64
        return httpx.Response(
            200, json={"images": [base64.b64encode(output.getvalue()).decode()]}
        )

    real = httpx.Client
    with patch(
        "assistant.image_worker.httpx.Client",
        side_effect=lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    ):
        assert image_worker.generate(row).startswith(b"\x89PNG")
    calls.clear()
    with patch("assistant.image_worker.idle", return_value=False):
        with pytest.raises(image_worker.ImageFailure) as error:
            image_worker.generate(row)
        assert error.value.code == "service_busy_or_unavailable"
    assert calls == []


def test_recovery_cannot_change_live_locked_job(user, image_mode):
    from pathlib import Path

    from companion.journal import WorkerLock

    row = ImageJob.objects.create(
        user=user,
        request_id="running",
        fingerprint="x",
        prompt="x",
        checkpoint="x",
        status="running",
    )
    path = Path(image_mode.MEDIA_ROOT).parent / "runtime" / "image-worker.lock"
    with WorkerLock(path):
        assert image_worker.recover_interrupted() is False
    row.refresh_from_db()
    assert row.status == "running"


def test_router_payload_decode_and_no_url_fetch(settings):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    settings.FREELLMAPI_API_KEY = "test-only"
    row = SimpleNamespace(checkpoint="@cf/bytedance/stable-diffusion-xl-lightning", prompt="A mug")
    output = io.BytesIO()
    Image.new("RGB", (1024, 1024)).save(output, format="PNG")
    body = {"model":row.checkpoint,"provider":"cloudflare","data":[{"b64_json":base64.b64encode(output.getvalue()).decode()}]}
    client = MagicMock()
    response = client.stream.return_value.__enter__.return_value
    response.status_code = 200
    response.iter_bytes.side_effect = lambda: iter([json.dumps(body).encode()])
    with patch("assistant.image_worker.httpx.Client") as factory:
        factory.return_value.__enter__.return_value = client
        assert image_worker.router_generate(row).startswith(b"\x89PNG")
        kwargs = client.stream.call_args.kwargs
        assert kwargs["json"]["model"] == row.checkpoint
        assert kwargs["json"]["n"] == 1
        assert "negative_prompt" not in kwargs["json"]
        body["data"] = [{"url":"http://127.0.0.1/private"}]
        with pytest.raises(image_worker.ImageFailure):
            image_worker.router_generate(row)
        client.get.assert_not_called()
        assert client.stream.call_count == 2
