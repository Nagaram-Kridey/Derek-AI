"""Google Identity Services credentials, bound to a one-use browser challenge.

No auto-link by email: Google's immutable subject identifies new tester accounts.
The existing owner retains its local password login and explicit staff privilege.
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .auth_models import GoogleIdentity, GoogleLoginChallenge
from .models import AssistantPreferences
from .permissions import is_admin
from .utils import audit, digest
from .views import LoginThrottle

logger = logging.getLogger(__name__)
COOKIE = "derek_google_challenge"


def identity(user):
    linked = GoogleIdentity.objects.filter(user=user).first()
    return {"username": (user.first_name or linked.email) if linked else user.username, "email": linked.email if linked else user.email,
            "is_admin": is_admin(user), "testing_workspace": getattr(settings, "TEST_WORKSPACE", False), "auth_provider": "google" if linked else "password"}


def verify_google_credential(credential):
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token
    class BoundedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 10
            return super().__call__(*args, **kwargs)
    return verify_oauth2_token(credential, BoundedRequest(), settings.GOOGLE_SIGN_IN_CLIENT_ID)


@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def config(request):
    return Response({"testing_workspace": getattr(settings, "TEST_WORKSPACE", False), "google_enabled": bool(settings.GOOGLE_SIGN_IN_CLIENT_ID),
                     "google_client_id": settings.GOOGLE_SIGN_IN_CLIENT_ID})


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([LoginThrottle])
def challenge(request):
    if not settings.GOOGLE_SIGN_IN_CLIENT_ID:
        return Response({"detail": "Google sign-in has not been configured."}, status=503)
    now = timezone.now()
    GoogleLoginChallenge.objects.filter(expires_at__lt=now).delete()
    challenge_id, nonce, binding = (secrets.token_urlsafe(32) for _ in range(3))
    GoogleLoginChallenge.objects.create(digest=digest(challenge_id), nonce_digest=digest(nonce),
        binding_digest=digest(binding), expires_at=now + timedelta(minutes=5))
    response = Response({"nonce": nonce, "challenge_id": challenge_id})
    response.set_cookie(COOKIE, binding, max_age=300, httponly=True,
                        secure=not settings.DEBUG, samesite="Strict", path="/v1/auth/google/")
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([LoginThrottle])
def google_login(request):
    if not settings.GOOGLE_SIGN_IN_CLIENT_ID:
        return Response({"detail": "Google sign-in has not been configured."}, status=503)
    credential = request.data.get("credential")
    challenge_id = request.data.get("challenge_id")
    if not isinstance(credential, str) or not 1 <= len(credential) <= 12000 or not isinstance(challenge_id, str) or len(challenge_id) > 100:
        return Response({"detail": "Google sign-in could not be verified. Please try again."}, status=401)
    row = GoogleLoginChallenge.objects.filter(digest=digest(challenge_id), consumed=False,
                                              expires_at__gt=timezone.now()).first()
    binding = request.COOKIES.get(COOKIE, "")
    if not row or not secrets.compare_digest(row.binding_digest, digest(binding)):
        logger.info("auth.google_failed: browser_challenge")
        return Response({"detail": "Google sign-in expired. Please try again."}, status=401)
    try:
        claims = verify_google_credential(credential)
        if (claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
                or claims.get("aud") != settings.GOOGLE_SIGN_IN_CLIENT_ID
                or not claims.get("sub") or not isinstance(claims["sub"], str) or len(claims["sub"]) > 255
                or claims.get("email_verified") is not True
                or not isinstance(claims.get("email"), str) or "@" not in claims["email"] or len(claims["email"]) > 254
                or not secrets.compare_digest(digest(str(claims.get("nonce", ""))), row.nonce_digest)):
            raise ValueError("Invalid identity claims")
    except Exception:  # noqa: BLE001 -- fail closed on verifier/network failures without exposing token data.
        # Never log credentials or provider exception text.
        logger.info("auth.google_failed: credential_verification")
        return Response({"detail": "Google sign-in could not be verified. Please try again."}, status=401)
    if getattr(settings, "TEST_WORKSPACE", False) and not getattr(settings, "TEST_OPEN_SIGNUP", False):
        invited = {email.strip().casefold() for email in getattr(settings, "TEST_INVITED_EMAILS", [])}
        if claims["email"].casefold() not in invited:
            logger.info("auth.google_failed: not_invited")
            return Response({"detail": "This Google account is not invited to this testing workspace."}, status=403)
    try:
        with transaction.atomic():
            if not GoogleLoginChallenge.objects.filter(pk=row.pk, consumed=False, expires_at__gt=timezone.now()).update(consumed=True):
                return Response({"detail": "Google sign-in expired. Please try again."}, status=401)
            linked = GoogleIdentity.objects.select_related("user").filter(subject=claims["sub"]).first()
            if linked:
                user = linked.user
                if not user.is_active:
                    return Response({"detail": "Google sign-in could not be verified. Please try again."}, status=401)
            else:
                if (getattr(settings, "TEST_WORKSPACE", False) and getattr(settings, "TEST_OPEN_SIGNUP", False)
                        and GoogleIdentity.objects.count() >= 10):
                    return Response({"detail": "This trial has reached its 10-account limit. Existing testers can still sign in."}, status=403)
                # Stable subject hash avoids email collisions and never selects a
                # legacy owner by email or makes the first visitor an admin.
                username = "google_" + hashlib.sha256(claims["sub"].encode()).hexdigest()[:32]
                user = get_user_model().objects.create_user(username=username, email=claims["email"],
                    first_name=str(claims.get("given_name", ""))[:150], password=None)
                linked = GoogleIdentity.objects.create(user=user, subject=claims["sub"], email=claims["email"])
                # Testers use the installation's configured route rather than
                # the historical Gemini-specific preference default.
                AssistantPreferences.objects.create(user=user, interactive_profile="configured")
            if getattr(settings, "TEST_WORKSPACE", False) and linked.email != claims["email"]:
                linked.email = claims["email"]
                linked.save(update_fields=["email"])
            token, _ = Token.objects.get_or_create(user=user)
            audit(user, "auth.google_login")
    except IntegrityError:
        return Response({"detail": "Google sign-in is already in progress. Please try again."}, status=409)
    response = Response({"token": token.key, **identity(user)})
    response.delete_cookie(COOKIE, path="/v1/auth/google/")
    return response


@api_view(["GET"])
def me(request):
    return Response(identity(request.user))
