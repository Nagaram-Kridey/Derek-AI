"""Isolated automated checks: never inherit the laptop's accounts or database."""

import os
import tempfile
from pathlib import Path

for name in (
    "GEMINI_API_KEY",
    "FREELLMAPI_API_KEY",
    "CARTESIA_API_KEY",
    "CARTESIA_VOICE_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_USER_ID",
    "TELEGRAM_WEBHOOK_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "CREDENTIAL_ENCRYPTION_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "LILYLEO_USER_TOKEN",
    "LILYLEO_DEVICE_TOKEN",
):
    os.environ[name] = ""
os.environ.update(
    DJANGO_DEBUG="true",
    DJANGO_SECRET_KEY="isolated-automated-checks-only-never-use-for-a-real-installation",
    DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
    DATABASE_URL=os.getenv("DEREK_TEST_DATABASE_URL", "sqlite:///:memory:"),
    DEREK_LOCAL_EXECUTION="false",
    DJANGO_SECURE_SSL_REDIRECT="false",
    MODEL_PROVIDER="gemini",
)

from .settings import *  # noqa: F403,E402

_media = tempfile.TemporaryDirectory(prefix="derek-test-media-")
MEDIA_ROOT = _media.name
STATIC_ROOT = str(Path(_media.name) / "staticfiles")
Path(STATIC_ROOT).mkdir()
WHITENOISE_ROOT = str(Path(_media.name) / "staticapp")
Path(WHITENOISE_ROOT).mkdir()
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
