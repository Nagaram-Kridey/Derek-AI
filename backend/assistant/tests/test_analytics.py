from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from assistant.analytics_views import analytics, latency_summary
from assistant.integrations.errors import ProviderError, RequestCancelled
from assistant.models import Command, Conversation, ModelObservation
from assistant.telemetry import record_observation
from assistant.utils import BudgetGateway


def request_analytics(user, days="7"):
    request = APIRequestFactory().get("/v1/admin/analytics/", {"days": days})
    if user:
        force_authenticate(request, user)
    return analytics(request)


@pytest.mark.django_db
def test_analytics_admin_permission_and_range(user):
    user.is_staff = False
    user.is_superuser = False
    assert request_analytics(user).status_code == 403
    assert request_analytics(None).status_code in {401, 403}
    user.is_staff = True
    for days in ["0", "31", "abc", "1.5"]:
        assert request_analytics(user, days).status_code == 400
    response = request_analytics(user)
    assert response.status_code == 200
    assert response.data["provider"]["latency_ms"] == {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    assert response.data["provider"]["collection_started_at"] is None


@pytest.mark.django_db
def test_latency_counts_command_queue_and_privacy(user):
    user.is_staff = True
    other = get_user_model().objects.create_user("tester", password=None)
    for latency, error in [(1000, None), (12000, ProviderError("secret api-key token prompt")),
                           (2000, RequestCancelled("secret"))]:
        record_observation(other, "freellmapi", "auto:fast", "chat", latency, error)
    old = ModelObservation.objects.create(user=user, provider="gemini", model_name="old", operation="chat", status="succeeded", latency_ms=900)
    ModelObservation.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))
    conversation = Conversation.objects.create(user=other, title="private title")
    command = Command.objects.create(user=other, conversation=conversation, request_id="test", input_text="private prompt", fingerprint="x", status="completed")
    now = timezone.now()
    Command.objects.filter(pk=command.pk).update(created_at=now-timedelta(seconds=8), started_at=now-timedelta(seconds=6), finished_at=now-timedelta(seconds=1))
    Command.objects.create(user=other, conversation=conversation, request_id="running", input_text="private", fingerprint="y", status="running")
    response = request_analytics(user).data
    assert response["provider"]["requests"] == 3
    assert response["provider"]["failed"] == 1
    assert response["provider"]["cancelled"] == 1
    assert response["provider"]["slow"] == 1
    assert response["provider"]["latency_ms"]["p50"] == 2000
    assert response["provider"]["latency_ms"]["p95"] == 12000
    assert len(response["models"]) == 1
    assert response["commands"]["queue_ms"]["p50"] == 2000
    assert response["commands"]["end_to_end_ms"]["p50"] == 7000
    assert response["commands"]["in_progress"] == 1
    assert response["users"] == {"total": 2, "active": 1}
    assert response["recent_issues"][0]["error_code"] == "cancelled"
    assert "secret" not in str(response)
    assert "private" not in str(response)
    assert other.username not in str(response)


@pytest.mark.django_db
def test_gateway_records_success_failure_and_does_not_mask_error(user, settings):
    settings.MODEL_PROVIDER = "freellmapi"
    gateway = SimpleNamespace(last_usage={}, last_routing={}, last_requested_model="auto:fast", chat=lambda: {"text": "private answer"})
    with patch("assistant.integrations.models.create_gateway", return_value=gateway):
        budget = BudgetGateway(user)
    assert budget.chat()["text"] == "private answer"
    assert ModelObservation.objects.get().status == "succeeded"
    def fail():
        raise ProviderError("secret provider URL/token")
    gateway.chat = fail
    with pytest.raises(ProviderError):
        budget.chat()
    assert ModelObservation.objects.count() == 2
    assert ModelObservation.objects.filter(status="failed", error_code="provider_error").exists()
    with patch("assistant.telemetry_models.ModelObservation.objects.create", side_effect=RuntimeError("private")), pytest.raises(ProviderError, match="secret provider"):
        budget.chat()


def test_percentiles_nearest_rank_and_safe_model_labels():
    assert latency_summary([1, 2, 3, 4])["p50"] == 2
    assert latency_summary(list(range(1, 101)))["p95"] == 95
    from assistant.telemetry import model_label
    assert model_label("https://secret.example/key") == "unknown"
