"""Dormant WhatsApp monitoring interfaces during core stabilization.

Stored settings preserve future preferences, never grant active permissions.
The companion does not import a monitor or call these endpoints.
"""
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from . import models as m
from .views import DeviceAuth
from .whatsapp_intents import settings_for


@api_view(['GET', 'POST'])
def preferences(request):
    if request.method == 'POST':
        return Response({'detail': 'WhatsApp monitoring and direct sending are deferred during stabilization.'}, status=409)
    row = settings_for(request.user)
    return Response({'direct_send': False, 'auto_watch': False, 'deferred': True,
        'saved_preferences': {'direct_send': row.direct_send, 'auto_watch': row.auto_watch, 'aliases': row.aliases},
        'watches': list(m.WhatsAppWatch.objects.filter(user=request.user).values(
            'id', 'recipient', 'active', 'state', 'last_checked_at', 'ack_state'))})


@api_view(['POST'])
@authentication_classes([DeviceAuth])
def sync(request):
    return Response({'watches': [], 'deferred': True})


@api_view(['POST'])
@authentication_classes([DeviceAuth])
def observe(request, pk):
    return Response({'detail': 'WhatsApp monitoring is deferred.'}, status=409)
