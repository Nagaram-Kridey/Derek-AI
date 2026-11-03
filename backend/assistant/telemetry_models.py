"""Content-free model observations. Prompts, responses and provider errors never belong here."""
import uuid

from django.conf import settings
from django.db import models


class ModelObservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    provider = models.CharField(max_length=24)
    model_name = models.CharField(max_length=160)
    operation = models.CharField(max_length=64)
    status = models.CharField(max_length=16)
    error_code = models.CharField(max_length=32, blank=True)
    latency_ms = models.PositiveIntegerField()

    class Meta:
        app_label = "assistant"
        ordering = ("-created_at",)
