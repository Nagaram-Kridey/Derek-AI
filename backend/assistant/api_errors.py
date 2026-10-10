from rest_framework.views import exception_handler as drf_handler
from rest_framework.response import Response
from pydantic import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from .integrations.errors import ConfigError, ProviderError

def exception_handler(exc, context):
    if isinstance(exc, ConfigError):
        return Response({"detail": str(exc)}, status=503)
    if isinstance(exc, ProviderError):
        return Response({"detail": str(exc)}, status=502)
    if isinstance(exc, (ValueError, ValidationError, DjangoValidationError)):
        return Response({"detail": str(exc)}, status=400)
    return drf_handler(exc, context)
