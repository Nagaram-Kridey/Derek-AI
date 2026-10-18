"""Deduplicate explicitly submitted create forms across a lost HTTP response."""

import re
from django.contrib.auth import get_user_model
from django.db import transaction
from . import models as m
from .utils import payload_digest


def create_once(user, kind, payload, model, create):
    request_id = payload.get("request_id")
    if request_id is None:
        return create(), True
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[A-Za-z0-9:_-]{1,128}", request_id
    ):
        raise ValueError("Provide a valid request_id for this form.")
    fingerprint = payload_digest(
        {key: value for key, value in payload.items() if key != "request_id"}
    )
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = m.FormRequest.objects.filter(
            user=user, kind=kind, request_id=request_id
        ).first()
        if previous:
            if previous.fingerprint != fingerprint:
                raise ValueError(
                    "This saved request belongs to different form values. Close this editor and start a new one before changing an unresolved request."
                )
            row = model.objects.filter(user=user, pk=previous.resource_id).first()
            if not row:
                raise ValueError(
                    "This request was already saved and later deleted. Start a new form to intentionally create another item."
                )
            return row, False
        row = create()
        m.FormRequest.objects.create(
            user=user,
            kind=kind,
            request_id=request_id,
            fingerprint=fingerprint,
            resource_id=row.pk,
        )
        return row, True
