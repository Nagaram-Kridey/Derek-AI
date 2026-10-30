"""Pure verification state for a single reviewed desktop message.

This deliberately does not drive input. An adapter must provide independently
verified UI evidence; OCR text changes alone are insufficient incoming evidence.
"""
from dataclasses import dataclass
import time


@dataclass
class MessageGuard:
    recipient: str
    message: str
    sent_anchor: str = ''
    deadline: float = 0
    acknowledgement_reserved: bool = False
    candidate: tuple | None = None

    def __post_init__(self):
        if not self.recipient.strip() or not self.message.strip():
            raise ValueError('Recipient and message are required.')
        if len(self.message) > 2000 or any(ord(c) < 32 for c in self.message):
            raise ValueError('Message must be plain single-line text under 2001 characters.')

    def verify_composer(self, *, recipient, unique, text, foreground, scope_valid, draft_empty):
        return (recipient == self.recipient and unique and text == self.message
                and foreground and scope_valid and draft_empty)

    def confirm_outgoing(self, anchor, *, exact_message, outgoing, now=None):
        if self.sent_anchor:
            raise ValueError('The outgoing message has already been confirmed.')
        if not anchor or not exact_message or not outgoing:
            raise ValueError('A verified new outgoing message is required.')
        self.sent_anchor = anchor
        self.deadline = (time.monotonic() if now is None else now) + 300

    def observe_reply(self, *, recipient, anchor, bubble_id, incoming, below_anchor,
                      at_bottom, stable_scope, now=None):
        now = time.monotonic() if now is None else now
        valid = (self.sent_anchor and now < self.deadline and not self.acknowledgement_reserved
                 and recipient == self.recipient and anchor == self.sent_anchor
                 and bubble_id and incoming and below_anchor and at_bottom and stable_scope)
        if not valid:
            self.candidate = None
            return False
        candidate = (recipient, anchor, bubble_id)
        if self.candidate != candidate:
            self.candidate = candidate
            return False
        # Reserve before input. The adapter must durably journal this reservation;
        # uncertain sends must never be retried after process recovery.
        self.acknowledgement_reserved = True
        return True
