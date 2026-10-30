"""Owner-authored messaging intents; no external message can grant authority."""
import re
from . import models as m


def settings_for(user):
    return m.WhatsAppSettings.objects.get_or_create(user=user)[0]


def route(command):
    text = command.input_text.strip()
    match = re.fullmatch(
        r'(?:please\s+)?send\s+(?:a\s+)?(?:whatsapp\s+(?:message|text)|(?:message|text)\s+(?:on|via)\s+whatsapp)'
        r'\s+to\s+(.{1,100}?)\s+(?:saying|that\s+says)\s*:?\s*(.{1,2000})', text, re.I)
    if match:
        recipient, message = match.groups()
        if message[:1] in {'"', "'"} and message[-1:] == message[:1]:
            message = message[1:-1]
    else:
        return None
    recipient = recipient.strip()
    return {'tool_calls': [{'name': 'send_whatsapp_message',
                           'args': {'recipient': recipient, 'message': message.strip()}}]}


def authorized_direct(command, args):
    # Retained preference is not an active permission during stabilization.
    return False


def controls(command):
    match = re.fullmatch(r'(?:please\s+)?(stop watching|watch|monitor)\s+(.{1,100})[.]?',
                        command.input_text.strip(), re.I)
    if not match:
        return None
    return ('Continuous WhatsApp monitoring is deferred during core reliability verification. '
            'No watch or acknowledgement was started. Exact one-time messages remain available with confirmation.')
