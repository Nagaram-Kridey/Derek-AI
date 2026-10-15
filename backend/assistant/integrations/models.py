"""Explicit model selection; local mode never falls back to a paid provider."""

from django.conf import settings

from .errors import ConfigError


def create_gateway():
    if settings.MODEL_PROVIDER == "gemini":
        from .gemini import GeminiGateway
        return GeminiGateway(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    if settings.MODEL_PROVIDER == "ollama":
        from .ollama import OllamaGateway
        return OllamaGateway(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL,
                             settings.OLLAMA_TIMEOUT_SECONDS, settings.OLLAMA_NUM_CTX)
    raise ConfigError("MODEL_PROVIDER must be gemini or ollama.")
