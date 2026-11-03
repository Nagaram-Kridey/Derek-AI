"""Private image jobs; accepted jobs retain quota/idempotency after deletion."""

import uuid

from django.conf import settings
from django.db import models


class ImageJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        "assistant.Conversation", null=True, blank=True, on_delete=models.SET_NULL
    )
    request_id = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    prompt = models.CharField(max_length=2000)
    negative_prompt = models.CharField(max_length=1000, blank=True)
    seed = models.BigIntegerField(default=-1)
    checkpoint = models.CharField(max_length=200)
    status = models.CharField(max_length=16, default="queued", db_index=True)
    error_code = models.CharField(max_length=40, blank=True)
    output = models.FileField(upload_to="images/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [  # noqa: RUF012 -- Django Meta declaration.
            models.UniqueConstraint(
                fields=["user", "request_id"], name="unique_image_request"
            )
        ]
        ordering = ["-created_at"]  # noqa: RUF012
