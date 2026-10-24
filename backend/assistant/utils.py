import hashlib
import json
import logging
import time
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from cryptography.fernet import Fernet
from .models import AuditEvent, ProviderCredential, UsageDay
from .integrations.errors import ConfigError, ProviderError

logger = logging.getLogger(__name__)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def audit(user, event, **detail):
    # Callers log identifiers and states, never raw prompts, tokens or file contents.
    AuditEvent.objects.create(user=user, event=event, detail=detail)

def payload_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))

def encrypt_credentials(user, provider, value):
    if not settings.CREDENTIAL_ENCRYPTION_KEY:
        raise ConfigError("Set CREDENTIAL_ENCRYPTION_KEY before connecting accounts.")
    ciphertext = Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode()).encrypt(json.dumps(value).encode()).decode()
    ProviderCredential.objects.update_or_create(user=user, provider=provider, defaults={"ciphertext": ciphertext})

def decrypt_credentials(user, provider):
    row = ProviderCredential.objects.filter(user=user, provider=provider).first()
    if not row:
        raise ConfigError(f"Connect {provider} in Settings first.")
    if not settings.CREDENTIAL_ENCRYPTION_KEY:
        raise ConfigError("Credential encryption key is unavailable.")
    return json.loads(Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode()).decrypt(row.ciphertext.encode()))

def reserve_usage(user, input_chars):
    with transaction.atomic():
        row, _ = UsageDay.objects.get_or_create(user=user, date=timezone.localdate())
        row = UsageDay.objects.select_for_update().get(pk=row.pk)
        if row.model_calls >= settings.DAILY_MODEL_CALL_LIMIT or row.input_chars + input_chars > settings.DAILY_INPUT_CHAR_LIMIT:
            raise ConfigError("Daily assistant usage limit reached. Review your limits in Settings.")
        row.model_calls += 1
        row.input_chars += input_chars
        row.save()
    return row.pk

class BudgetGateway:
    """Count every provider call, including internal research calls, before sending."""
    def __init__(self, user, profile=None, cancelled=None):
        from .integrations.models import create_gateway
        self.user = user
        self.gateway = create_gateway(profile)
        self.provider = "gemini" if profile == "gemini" else settings.MODEL_PROVIDER
        self.cancelled = cancelled
        self.gateway.cancelled = cancelled

    def __getattr__(self, name):
        method = getattr(self.gateway, name)
        def call(*args, **kwargs):
            from django.db.models import F
            from .integrations.errors import RequestCancelled
            if self.cancelled and self.cancelled():
                raise RequestCancelled("Research cancelled.")
            pk = reserve_usage(self.user, len(json.dumps([args, kwargs], default=str)))
            started = time.monotonic()
            try:
                result = method(*args, **kwargs)
                if name == "chat" and isinstance(result, dict):
                    result["provider_latency_ms"] = round((time.monotonic() - started) * 1000)
                if self.cancelled and self.cancelled():
                    raise RequestCancelled("Research cancelled.")
                if name != "grounded_search":
                    self._health(True)
                    if self.provider == "freellmapi" and self.gateway.last_routing:
                        audit(self.user, "model.routed", operation=name, **self.gateway.last_routing)
                return result
            except (ConfigError, ProviderError) as exc:
                if name != "grounded_search":
                    self._health(False, str(exc))
                raise
            finally:
                usage = self.gateway.last_usage
                UsageDay.objects.filter(pk=pk).update(input_tokens=F("input_tokens") + usage.get("input_tokens", 0), output_tokens=F("output_tokens") + usage.get("output_tokens", 0))
                self.gateway.last_usage = {"input_tokens": 0, "output_tokens": 0}
        return call

    def _health(self, succeeded, error=""):
        from .models import ModelHealth
        model_name = {"gemini": settings.GEMINI_MODEL, "ollama": settings.OLLAMA_MODEL,
                      "freellmapi": settings.FREELLMAPI_MODEL}.get(self.provider, "")
        if self.provider == "freellmapi":
            model_name = self.gateway.last_requested_model
        changes = {"last_success_at" if succeeded else "last_failure_at": timezone.now()}
        if not succeeded:
            changes["error"] = error[:1000]
        ModelHealth.objects.update_or_create(user=self.user, provider=self.provider, model_name=model_name, defaults=changes)

def kick(task, *args):
    if settings.LOCAL_EXECUTION:
        # The local supervisor's lanes poll the same durable outbox rows. Do
        # not create a second delivery path or require a broker on the laptop.
        return
    def publish():
        try:
            task.delay(*args)
        except Exception:
            # Pending rows survive a broker outage; Beat republishes them later.
            logger.warning("Job saved; broker unavailable. Scheduler will dispatch pending work.")
    # A worker must never see an event before its database record commits.
    transaction.on_commit(publish)
