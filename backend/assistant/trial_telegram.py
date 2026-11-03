"""Dedicated trial bot: one-use private-chat linking and owned text conversations.

Link secrets are bearer challenges (five minute lifetime), only their digest is
stored. Never use personal TELEGRAM_* settings or user-supplied destinations.
"""
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .integrations.telegram import _call, send_message
from .models import Command
from .permissions import trial_admitted
from .telegram_link_models import (
    TelegramLink,
    TelegramLinkGrant,
    TrialTelegramCursor,
    TrialTelegramReceipt,
)
from .utils import audit, digest


def configured():
    return bool(getattr(settings, 'TEST_WORKSPACE', False) and getattr(settings, 'TEST_TELEGRAM_BOT_TOKEN', '') and re.fullmatch(r'[A-Za-z0-9_]{5,32}', getattr(settings, 'TEST_TELEGRAM_BOT_USERNAME', '')))


@api_view(['GET', 'POST', 'DELETE'])
def link(request):
    if not getattr(settings, 'TEST_WORKSPACE', False):
        return Response({'detail':'This connection is for the testing workspace.'}, status=404)
    row = TelegramLink.objects.filter(user=request.user).first()
    if request.method == 'DELETE':
        TelegramLink.objects.filter(user=request.user).delete()
        TelegramLinkGrant.objects.filter(user=request.user).delete()
        audit(request.user, 'telegram.disconnected')
        return Response({'connected':False, 'configured':configured(), 'username':''})
    if request.method == 'GET':
        return Response({'configured':configured(), 'connected':bool(row), 'username':row.username if row else ''})
    if not configured():
        return Response({'detail':'The test administrator must configure a dedicated Telegram bot first.'}, status=409)
    raw = secrets.token_urlsafe(32)
    expires = timezone.now() + timedelta(minutes=5)
    with transaction.atomic():
        TelegramLinkGrant.objects.filter(user=request.user).delete()
        TelegramLinkGrant.objects.create(user=request.user, digest=digest(raw), expires_at=expires)
    return Response({'url':'https://t.me/'+settings.TEST_TELEGRAM_BOT_USERNAME+'?start='+raw, 'expires_at':expires})


def deliver(user, command):
    if not configured() or not trial_admitted(user):
        raise ValueError('Telegram connection unavailable.')
    row = TelegramLink.objects.filter(user=user).first()
    if not row:
        raise ValueError('Connect your Telegram account first.')
    text = command.response.get('reply_text', '')
    if command.user_id != user.pk or command.status != 'completed' or not text or command.response.get('action_proposals'):
        raise ValueError('Only your completed plain answers can be sent.')
    return send_message(settings.TEST_TELEGRAM_BOT_TOKEN, row.chat_id, text[:16000])


@api_view(['POST'])
def send(request):
    command = get_object_or_404(Command, user=request.user, pk=request.data.get('command_id'))
    try:
        deliver(request.user, command)
    except ValueError as exc:
        return Response({'detail':str(exc)}, status=409)
    audit(request.user, 'telegram.answer_sent', command_id=str(command.pk))
    return Response({'sent':True})


def handle_update(update):
    message = update.get('message') or {}
    chat, sender = message.get('chat') or {}, message.get('from') or {}
    if chat.get('type') != 'private' or sender.get('is_bot') or str(chat.get('id')) != str(sender.get('id')):
        return
    chat_id = str(chat['id'])
    text = message.get('text') or ''
    if not isinstance(text, str) or len(text) > 12000:
        return
    update_id = update.get('update_id')
    if not isinstance(update_id, int):
        return
    with transaction.atomic():
        receipt, created = TrialTelegramReceipt.objects.get_or_create(update_id=update_id, defaults={'chat_id':chat_id})
        if not created:
            return
        if text.startswith('/start '):
            secret = text.split(' ', 1)[1]
            grant = TelegramLinkGrant.objects.select_related('user').filter(digest=digest(secret), consumed=False, expires_at__gt=timezone.now()).first()
            if not grant or not trial_admitted(grant.user):
                return
            # Existing private chats cannot be reassigned to another web user.
            if TelegramLink.objects.filter(chat_id=chat_id).exclude(user=grant.user).exists():
                return
            if not TelegramLinkGrant.objects.filter(pk=grant.pk, consumed=False).update(consumed=True):
                return
            TelegramLink.objects.update_or_create(user=grant.user, defaults={'chat_id':chat_id, 'telegram_user_id':str(sender['id']), 'username':str(sender.get('username') or sender.get('first_name') or 'Connected account')[:100]})
            receipt.status='linked'; receipt.save(update_fields=['status'])
            audit(grant.user, 'telegram.connected')
            return
        binding = TelegramLink.objects.select_related('user').filter(chat_id=chat_id, telegram_user_id=str(sender['id'])).first()
        if not binding or not trial_admitted(binding.user) or not text.strip():
            return
        from .commands import submit
        try:
            command, _ = submit(binding.user, text, request_id='trial-tg-'+str(update_id), channel='telegram', external_key=chat_id, profile='configured')
        except ValueError:
            receipt.status='rejected'; receipt.save(update_fields=['status']); return
        receipt.command=command; receipt.status='pending'; receipt.save(update_fields=['command','status'])


def poll_once():
    if not configured():
        return
    cursor, _ = TrialTelegramCursor.objects.get_or_create(pk=1)
    info = _call(settings.TEST_TELEGRAM_BOT_TOKEN, 'getWebhookInfo', json={})
    if info.get('url'):
        return  # Never remove or compete with a webhook configured elsewhere.
    updates = _call(settings.TEST_TELEGRAM_BOT_TOKEN, 'getUpdates', json={'offset':cursor.offset, 'timeout':0, 'limit':20, 'allowed_updates':['message']})
    for update in updates:
        try:
            handle_update(update)
        except IntegrityError:
            pass
        cursor.offset=max(cursor.offset, int(update['update_id'])+1)
        cursor.save(update_fields=['offset'])
    for receipt in TrialTelegramReceipt.objects.filter(status='pending', command__status__in=['completed','failed','cancelled']).select_related('command__user')[:20]:
        # Claim before network I/O. Unknown outcomes are never blindly replayed.
        if not TrialTelegramReceipt.objects.filter(pk=receipt.pk,status='pending').update(status='sending'):
            continue
        try:
            deliver(receipt.command.user, receipt.command)
            status='sent'
        except Exception:  # noqa: BLE001 -- unknown network outcomes must not be replayed.
            status='needs_attention'
        TrialTelegramReceipt.objects.filter(pk=receipt.pk).update(status=status)
