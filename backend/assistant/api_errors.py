from rest_framework.views import exception_handler as drf_handler
from rest_framework.response import Response
from pydantic import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from .integrations.errors import ConfigError, ProviderError
import logging

def exception_handler(exc, context):
    if isinstance(exc, ConfigError):
        return Response({"detail": str(exc)}, status=503)
    if isinstance(exc, ProviderError):
        return Response({"detail": str(exc)}, status=502)
    if isinstance(exc, ValidationError):
        detail = "; ".join(".".join(str(part) for part in item["loc"]) + ": " + item["msg"] for item in exc.errors(include_input=False, include_url=False))
        return Response({"detail": detail}, status=400)
    if isinstance(exc, (ValueError, DjangoValidationError)):
        return Response({"detail": str(exc)}, status=400)
    response = drf_handler(exc, context)
    if response is None:
        logging.getLogger(__name__).error("API request could not complete (%s)", type(exc).__name__)
        return Response({"detail": "This request could not finish. Its saved command, if accepted, is available in Command history. Retrieve it before submitting another action."}, status=500)
    return response
