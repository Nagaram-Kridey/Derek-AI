from django.conf import settings
from django.db import models


class TelegramLink(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chat_id = models.CharField(max_length=24, unique=True)
    telegram_user_id = models.CharField(max_length=24, unique=True)
    username = models.CharField(max_length=100, blank=True)

class TelegramLinkGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)

class TrialTelegramReceipt(models.Model):
    update_id = models.BigIntegerField(primary_key=True)
    command = models.OneToOneField('assistant.Command', null=True, on_delete=models.SET_NULL)
    chat_id = models.CharField(max_length=24)
    status = models.CharField(max_length=24, default='received')

class TrialTelegramCursor(models.Model):
    offset = models.BigIntegerField(default=0)
