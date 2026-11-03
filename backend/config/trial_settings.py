"""Isolated manual tester workspace. Never loads the personal .env file."""
import json
import os
from pathlib import Path

TRIAL_ROOT = Path(__file__).resolve().parents[2] / '.trial-workspace'
config_file = TRIAL_ROOT / 'config.json'
if not config_file.exists():
    raise RuntimeError('Test workspace is not initialized. Run python -m testing_workspace init.')
_trial = json.loads(config_file.read_text(encoding='utf-8'))
# Seed only bootstrap values needed for base validation. All sensitive settings
# below are explicitly overwritten, including any inherited shell variables.
os.environ['DJANGO_SECRET_KEY'] = _trial['secret_key']
os.environ['DEREK_LOCAL_EXECUTION'] = 'true'
os.environ['DJANGO_DEBUG'] = 'false'
from .settings import *  # noqa: F403,E402

TEST_WORKSPACE = True
TEST_OPEN_SIGNUP = bool(_trial.get("open_signup", False))
DEBUG = False
SECRET_KEY = _trial['secret_key']
CREDENTIAL_ENCRYPTION_KEY = _trial['encryption_key']
TEST_INVITED_EMAILS = {email.strip().casefold() for email in _trial.get('invited_emails', [])}
if len(TEST_INVITED_EMAILS) > 10:
    raise RuntimeError('At most 10 tester emails are allowed. Edit trial configuration.')
TEST_DAILY_CALL_LIMIT = DAILY_MODEL_CALL_LIMIT = 20
TEST_SHARED_DAILY_CALL_LIMIT = 200
TIME_ZONE = 'Asia/Kolkata'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(TRIAL_ROOT / 'db.sqlite3'), 'OPTIONS': {'timeout': 30, 'transaction_mode': 'IMMEDIATE'}}}
MEDIA_ROOT = TRIAL_ROOT / 'media'
STATIC_ROOT = TRIAL_ROOT / 'static'
WHITENOISE_ROOT = TRIAL_ROOT / 'dashboard'
LOCAL_EXECUTION = True
GOOGLE_SIGN_IN_CLIENT_ID = _trial.get('google_client_id', '')
GOOGLE_CLIENT_ID = GOOGLE_CLIENT_SECRET = GOOGLE_REDIRECT_URI = ''
TELEGRAM_BOT_TOKEN = TELEGRAM_CHAT_ID = TELEGRAM_USER_ID = TELEGRAM_WEBHOOK_SECRET = ''
CARTESIA_API_KEY = CARTESIA_VOICE_ID = GEMINI_API_KEY = ''
MODEL_PROVIDER = _trial.get('text_provider', 'freellmapi')
if MODEL_PROVIDER not in {'freellmapi', 'custom'}:
    raise RuntimeError('Unsupported trial text provider.')
CUSTOM_LLM_BASE_URL = _trial.get('custom_llm_base_url', '')
CUSTOM_LLM_MODEL = _trial.get('custom_llm_model', '')
CUSTOM_LLM_API_KEY = _trial.get('custom_llm_api_key', '')
CUSTOM_LLM_TIMEOUT_SECONDS = 120
CUSTOM_LLM_SUPPORTS_TOOLS = _trial.get('custom_llm_supports_tools', False) is True
CUSTOM_LLM_SUPPORTS_JSON_SCHEMA = _trial.get('custom_llm_supports_json_schema', False) is True
FREELLMAPI_API_KEY = _trial.get('router_key', '')
FREELLMAPI_BASE_URL = 'http://127.0.0.1:3001/v1'
FREELLMAPI_MODEL = FREELLMAPI_RESEARCH_MODEL = 'auto:fast'
FREELLMAPI_TIMEOUT_SECONDS = 60
CELERY_TASK_ALWAYS_EAGER = False
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
_public = _trial.get('public_host', '')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost'] + ([_public] if _public else [])
CSRF_TRUSTED_ORIGINS = ['https://' + _public] if _public else []
SECURE_SSL_REDIRECT = False  # loopback HTTP health/admin bootstrap; public edge is HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 0  # trial hostname must not impose policy on future subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_PRELOAD = False

# Dedicated trial bot only; no personal Telegram credential fallback.
TEST_TELEGRAM_BOT_TOKEN = _trial.get("telegram_bot_token", "")
TEST_TELEGRAM_BOT_USERNAME = _trial.get("telegram_bot_username", "")

# Image generation stays disabled until pinned-model feasibility evidence passes.
from testing_workspace.image_service import validated_gate
_image_gate = validated_gate()
TEST_IMAGE_ENABLED = _image_gate['enabled']
TEST_IMAGE_CHECKPOINT = _image_gate['checkpoint']
TEST_IMAGE_CHECKPOINT_SHA256 = _image_gate['checkpoint']
TEST_IMAGE_DISABLED_REASON = _image_gate['reason']

TEST_IMAGE_PROVIDER = _trial.get('image_provider', 'a1111')
TEST_IMAGE_MODEL = _trial.get('image_model', '@cf/bytedance/stable-diffusion-xl-lightning')
if TEST_IMAGE_PROVIDER == 'freellmapi':
    TEST_IMAGE_ENABLED = _trial.get('images_enabled', False) is True and bool(FREELLMAPI_API_KEY)
    TEST_IMAGE_DISABLED_REASON = '' if TEST_IMAGE_ENABLED else 'Configure the local image router before generating.'
