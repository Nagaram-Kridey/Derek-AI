"""One-use local launch exchange, issued only to an authenticated launcher."""
from datetime import timedelta
import hashlib
import re
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import DesktopLaunchGrant
from .utils import audit

ORIGIN = 'http://127.0.0.1:8000'


def local_request(request, *, exchange=False):
    return (settings.LOCAL_EXECUTION and request.META.get('REMOTE_ADDR') == '127.0.0.1'
            and request.get_host() == '127.0.0.1:8000'
            and request.headers.get('Origin') == (ORIGIN if exchange else None)
            and not request.headers.get('X-Forwarded-For')
            and request.content_type == 'application/json')


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
def launch(request):
    if not local_request(request):
        return Response({'detail':'Desktop launch is available to the local launcher only.'}, status=403)
    now = timezone.now()
    DesktopLaunchGrant.objects.filter(expires_at__lt=now).delete()
    # Keep one outstanding handoff per owner, invalidating old launch tabs.
    code = secrets.token_urlsafe(32)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        DesktopLaunchGrant.objects.filter(user=request.user).delete()
        DesktopLaunchGrant.objects.create(user=request.user, digest=hashed(code), token_digest=hashed(request.auth.key), expires_at=now+timedelta(seconds=45))
    audit(request.user, 'auth.desktop_launch_issued')
    return Response({'code':code}, headers={'Cache-Control':'no-store'})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def exchange(request):
    if not local_request(request, exchange=True):
        return Response({'detail':'Invalid desktop launch origin.'},status=403)
    if not isinstance(request.data,dict):
        return Response({'detail':'Send a JSON object with a desktop launch code.'},status=400)
    code = request.data.get('code')
    if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',code):
        return Response({'detail':'Desktop sign-in expired. Reopen Derek from the tray.'},status=401)
    row = DesktopLaunchGrant.objects.filter(digest=hashed(code), consumed=False, expires_at__gt=timezone.now()).first()
    if not row or not DesktopLaunchGrant.objects.filter(pk=row.pk,consumed=False,expires_at__gt=timezone.now()).update(consumed=True):
        return Response({'detail':'Desktop sign-in expired. Reopen Derek from the tray.'},status=401)
    token = Token.objects.select_related('user').filter(user=row.user,user__is_active=True).first()
    if not token or not secrets.compare_digest(hashed(token.key),row.token_digest):
        return Response({'detail':'Sign in again to reconnect this desktop.'},status=401)
    audit(token.user,'auth.desktop_launch_exchanged')
    return Response({'token':token.key,'username':token.user.username},headers={'Cache-Control':'no-store'})
