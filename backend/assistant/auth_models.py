"""Google identity is separate from personal calendar credentials."""
from django.conf import settings
from django.db import models


class GoogleIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_identity")
    subject = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)


class GoogleLoginChallenge(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    nonce_digest = models.CharField(max_length=64)
    binding_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)
