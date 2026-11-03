"""Best-effort, content-free observations around the existing budgeted provider boundary."""
import logging
import re

from django.db import transaction

from .integrations.errors import ConfigError, ProviderError, RequestCancelled

logger = logging.getLogger(__name__)


def model_label(value):
    value = str(value or "")
    return value if re.fullmatch(r"[A-Za-z0-9_.:/@-]{1,160}", value) and "://" not in value else "unknown"


def error_code(error):
    if error is None:
        return ""
    if isinstance(error, RequestCancelled):
        return "cancelled"
    if isinstance(error, (TimeoutError,)):
        return "timeout"
    if isinstance(error, ConfigError):
        return "configuration"
    if isinstance(error, ProviderError):
        return "provider_error"
    return "unexpected_error"


def record_observation(user, provider, model, operation, elapsed_ms, error=None):
    from .telemetry_models import ModelObservation
    code = error_code(error)
    try:
        with transaction.atomic():
            ModelObservation.objects.create(
                user=user,
                provider=provider if provider in {"gemini", "ollama", "freellmapi", "custom"} else "unknown",
                model_name=model_label(model),
                operation=operation if re.fullmatch(r"[a-z_]{1,64}", operation) else "unknown",
                status="cancelled" if code == "cancelled" else "failed" if code else "succeeded",
                error_code=code,
                latency_ms=max(0, round(elapsed_ms)),
            )
    except Exception:  # noqa: BLE001 -- observational failures must not affect user requests
        # Telemetry failure must not mask a generated answer/provider failure or log secrets.
        logger.warning("Model observation could not be saved.")
