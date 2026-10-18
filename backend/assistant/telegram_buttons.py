"""Compact signed buttons bound to an immutable, owner-scoped proposal."""

import base64
import hashlib
import hmac
import re
import uuid
from django.conf import settings
from . import models as m


def _signature(proposal, action):
    value = f"{proposal.pk}:{proposal.revision}:{proposal.payload_digest}:{proposal.user_id}:{action}"
    return (
        base64.urlsafe_b64encode(
            hmac.new(
                settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256
            ).digest()[:12]
        )
        .decode()
        .rstrip("=")
    )


def button_data(proposal, action):
    identifier = base64.urlsafe_b64encode(proposal.id.bytes).decode().rstrip("=")
    return f"d:{identifier}:{proposal.revision}:{action}:{_signature(proposal, action)}"


def markup(proposal):
    return {
        "inline_keyboard": [
            [
                {"text": "Confirm change", "callback_data": button_data(proposal, "y")},
                {"text": "Cancel", "callback_data": button_data(proposal, "n")},
            ]
        ]
    }


def resolve(user, data):
    match = re.fullmatch(
        r"d:([A-Za-z0-9_-]{22}):([0-9]{1,10}):([yn]):([A-Za-z0-9_-]{16})", data
    )
    if not match:
        raise ValueError("This button is not a current action confirmation.")
    encoded, revision, action, signature = match.groups()
    identifier = uuid.UUID(bytes=base64.urlsafe_b64decode(encoded + "=="))
    proposal = m.ActionProposal.objects.filter(
        user=user, pk=identifier, action__command__channel="telegram"
    ).first()
    if (
        not proposal
        or proposal.revision != int(revision)
        or not hmac.compare_digest(signature, _signature(proposal, action))
    ):
        raise ValueError("This action changed. Ask for a fresh readback.")
    return proposal, action == "y"
