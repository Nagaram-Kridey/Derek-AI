"""Owner-scoped personal facts: local extraction, indexed recall, no model calls."""

import hashlib
import json
import re
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from . import models as m
from .utils import audit

LIMIT = 200
STOP = set("a an the is are am i me my you your of for to in on and or that this it what how do does please about remember memory with have has".split())
SECRET = re.compile(r"\b(password|passcode|otp|api[ _-]?key|access[ _-]?token|secret[ _-]?key|private[ _-]?key|recovery[ _-]?code|seed phrase)\b|(?:sk-|AIza|ghp_|github_pat_|freellmapi-)[A-Za-z0-9_-]{12,}|\b\d{6,}:[A-Za-z0-9_-]{20,}|-----BEGIN|\b[a-fA-F0-9]{32,}\b", re.I)
PATTERNS = [
    (r"(?:my name is|call me) (.+)", "profile.name", "Name"),
    (r"(?:i work as|my job is|my role is) (.+)", "profile.role", "Work role"),
    (r"(?:i am working on|i'm working on|my project is) (.+)", "profile.project", "Current project"),
    (r"my preferred programming language is (.+)", "preference.programming_language", "Programming language"),
    (r"my preferred language is (.+)", "preference.language", "Reply language"),
    (r"i prefer (.{1,200}(?:answers|replies|responses).{0,100})", "preference.reply_style", "Reply preference"),
    (r"i prefer (.+)", None, "Preference"),
]


def tokens(text):
    return {word[:-1] if word.endswith("s") and len(word) > 4 else word
            for word in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,39}", text.casefold()) if word not in STOP}


def validate_content(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ValueError("A memory must contain 1–500 characters.")
    value = " ".join(value.split())
    if SECRET.search(value):
        raise ValueError("Credentials, keys and recovery codes cannot be saved as personal memories.")
    return value


def fingerprint(key, content):
    return hashlib.sha256((key + "\n" + " ".join(content.casefold().split())).encode()).hexdigest()


def parse_fact(text, *, explicit=False):
    text = text.strip().rstrip(".! ")
    if not text or len(text) > 500 or "\n" in text or SECRET.search(text):
        return None
    for pattern, key, title in PATTERNS:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            value = match[1].strip()
            if not value or re.search(r"\b(example|pretend|hypothetically|ignore|instructions|system prompt)\b", text, re.I):
                return None
            key = key or "preference." + hashlib.sha256(value.casefold().encode()).hexdigest()[:20]
            return {"key": key, "title": title, "content": text, "pinned": True}
    if explicit:
        if ":" in text:
            title, value = text.split(":", 1)
            title = title.strip()
            if not 1 <= len(title) <= 80 or not value.strip():
                raise ValueError("Use Remember label: detail, with a short label.")
            aliases = {"name": "profile.name", "work role": "profile.role", "project": "profile.project",
                       "current project": "profile.project", "reply language": "preference.language",
                       "programming language": "preference.programming_language", "reply preference": "preference.reply_style"}
            key = aliases.get(title.casefold()) or "custom." + hashlib.sha256(title.casefold().encode()).hexdigest()[:24]
            return {"key": key, "title": title, "content": value.strip(), "pinned": title.casefold() in aliases}
        return {"key": "fact." + hashlib.sha256(text.casefold().encode()).hexdigest()[:24],
                "title": text[:80], "content": text, "pinned": False}
    return None


def _lock(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)


def _forget(row):
    m.ForgottenMemory.objects.get_or_create(user=row.user, fingerprint=row.fingerprint)
    identifier = str(row.pk)
    row.delete()
    audit(row.user, "memory.forgotten", memory_id=identifier)


def _index(row):
    row.terms.all().delete()
    m.MemoryTerm.objects.bulk_create([m.MemoryTerm(memory=row, token=token)
                                    for token in sorted(tokens(row.title + " " + row.content))[:80]])


def store(user, fact, *, status="suggested", source=None, explicit=False):
    content = validate_content(fact["content"])
    digest = fingerprint(fact["key"], content)
    with transaction.atomic():
        _lock(user)
        if m.ForgottenMemory.objects.filter(user=user, fingerprint=digest).exists():
            if not explicit:
                return None
            m.ForgottenMemory.objects.filter(user=user, fingerprint=digest).delete()
        row = m.PersonalMemory.objects.filter(user=user, fingerprint=digest).first()
        # Backfill/automatic suggestions never downgrade an accepted fact.
        if row and (status == "suggested" or row.status == "active"):
            if explicit and source is not None:
                row.source_message, row.version = source, row.version + 1
                row.save(update_fields=["source_message", "version", "updated_at"])
            return row
        if status == "active":
            for previous in m.PersonalMemory.objects.filter(user=user, key=fact["key"], status="active"):
                if not row or previous.pk != row.pk:
                    _forget(previous)
        if m.PersonalMemory.objects.filter(user=user, status=status).count() >= LIMIT:
            raise ValueError(f"The {status} memory limit is {LIMIT}. Review or forget older memories first.")
        if row:
            row.status, row.version = status, row.version + 1
            row.save(update_fields=["status", "version", "updated_at"])
        else:
            row = m.PersonalMemory.objects.create(user=user, key=fact["key"], title=fact["title"],
                content=content, fingerprint=digest, status=status, pinned=fact.get("pinned", False), source_message=source)
            _index(row)
        audit(user, "memory.saved", memory_id=str(row.pk), status=status)
        return row


def update(user, identifier, values):
    with transaction.atomic():
        _lock(user)
        row = m.PersonalMemory.objects.select_for_update().filter(user=user, pk=identifier).first()
        if not row:
            raise ValueError("This memory no longer exists.")
        if type(values.get("version")) is not int or values["version"] != row.version:
            raise ValueError("This memory changed. Refresh before editing it.")
        if set(values) - {"version", "content", "title", "status", "pinned"}:
            raise ValueError("Unsupported memory field.")
        status = values.get("status", row.status)
        if status not in {"active", "suggested"}:
            raise ValueError("Choose active or suggested.")
        content = validate_content(values.get("content", row.content))
        title = values.get("title", row.title)
        pinned = values.get("pinned", row.pinned)
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100 or type(pinned) is not bool:
            raise ValueError("Use a short title and a true/false pinned value.")
        validate_content(title)
        digest = fingerprint(row.key, content)
        if m.PersonalMemory.objects.filter(user=user, fingerprint=digest).exclude(pk=row.pk).exists():
            raise ValueError("That memory already exists.")
        if status == "active" and row.status != "active" and m.PersonalMemory.objects.filter(user=user, status="active").count() >= LIMIT:
            raise ValueError("Review or forget an active memory first; the limit is 200.")
        if status == "active":
            for previous in m.PersonalMemory.objects.filter(user=user, key=row.key, status="active").exclude(pk=row.pk):
                _forget(previous)
        if digest != row.fingerprint:
            m.ForgottenMemory.objects.get_or_create(user=user, fingerprint=row.fingerprint)
        if content != row.content or title.strip() != row.title:
            # An owner's correction is now a manual fact, not a claim copied
            # verbatim from its original chat message.
            row.source_message = None
        row.content, row.title, row.status, row.pinned = content, title.strip(), status, pinned
        row.fingerprint, row.version = digest, row.version + 1
        row.save()
        _index(row)
        audit(user, "memory.updated", memory_id=str(row.pk), version=row.version)
        return row


def forget(user, identifier, version):
    with transaction.atomic():
        _lock(user)
        row = m.PersonalMemory.objects.filter(user=user, pk=identifier).first()
        if not row:
            return
        if type(version) is not int or row.version != version:
            raise ValueError("This memory changed. Refresh before forgetting it.")
        _forget(row)


def recall(user, query):
    query_tokens = sorted(tokens(query))[:24]
    rows = (m.PersonalMemory.objects.filter(user=user, status="active")
            .filter(Q(pinned=True) | Q(terms__token__in=query_tokens))
            .annotate(matches=Count("terms", filter=Q(terms__token__in=query_tokens), distinct=True))
            .order_by("-matches", "-pinned", "-updated_at")[:12])
    selected, size = [], 0
    for row in rows:
        item = {"id": str(row.pk), "detail": row.content, "title": row.title}
        length = len(json.dumps(item, ensure_ascii=False))
        if size + length > 1800:
            continue
        selected.append(item)
        size += length
        if len(selected) == 5:
            break
    return selected


def import_previous(user):
    from .capabilities import preferences
    if not preferences(user).memory_suggestions:
        raise ValueError("Enable memory suggestions before scanning previous chats.")
    # Local deterministic scan, bounded independently of lifetime history size.
    rows = (m.Message.objects.filter(conversation__user=user, role="user")
            .order_by("-created_at", "-id")[:500])
    count = 0
    for message in rows:
        remembered = re.fullmatch(r"(?:/remember\s+|remember\s+that\s+|remember:\s*|remember\s+)(.+)", message.content.strip(), re.I | re.S)
        try:
            fact = parse_fact(remembered[1], explicit=True) if remembered else parse_fact(message.content)
        except ValueError:
            continue
        if fact:
            digest = fingerprint(fact["key"], fact["content"])
            if m.PersonalMemory.objects.filter(user=user, fingerprint=digest).exists():
                continue
            if m.PersonalMemory.objects.filter(user=user, status="suggested").count() >= LIMIT:
                break
            if store(user, fact, source=message):
                count += 1
    audit(user, "memory.history_scanned", suggestions=count)
    return count


def process(command, message):
    """Local commands and suggestions run before inference for all online channels."""
    from .capabilities import preferences
    from .commands import ensure_active
    pref = preferences(command.user)
    text = command.input_text.strip()
    remember = re.fullmatch(r"(?:/remember\s+|remember\s+that\s+|remember:\s*|remember\s+)(.+)", text, re.I | re.S)
    listing = text.casefold().rstrip(".!?") in {"/memories", "what do you remember about me", "show my memories"}
    forgetting = re.fullmatch(r"(?:/forget\s+|forget\s+(?:the memory\s+)?)(.+)", text, re.I)
    candidate = parse_fact(text) if pref.memory_enabled and pref.memory_suggestions else None
    if not (remember or listing or forgetting or candidate):
        return None
    with transaction.atomic():
        _lock(command.user)
        ensure_active(command)
        pref.refresh_from_db(fields=["memory_enabled", "memory_suggestions"])
        if remember:
            if not pref.memory_enabled:
                return "Shared memory is paused. Enable it in Settings → Memory before saving a detail."
            fact = parse_fact(remember[1], explicit=True)
            if not fact:
                return "I couldn't save that as a personal memory. Use Remember label: short detail. Never include credentials or API keys."
            row = store(command.user, fact, status="active", source=message, explicit=True)
            return f"Remembered: {row.content}\n\nThis detail is shared across your normal web, Telegram and voice chats. Manage it in Settings → Memory."
        if listing:
            rows = list(m.PersonalMemory.objects.filter(user=command.user, status="active").order_by("-updated_at")[:12])
            return ("Shared memory is " + ("on." if pref.memory_enabled else "paused.") + "\n\n" +
                    ("\n".join(f"{row.title}: {row.content}" for row in rows) or "No accepted personal memories yet. Say Remember label: detail."))
        match = forgetting
        if match:
            target = match[1].strip().rstrip(".!?")
            rows = list(m.PersonalMemory.objects.filter(user=command.user).filter(Q(title__iexact=target) | Q(content__iexact=target))[:2])
            if len(rows) != 1:
                return "Use the exact memory title or detail after Forget, or choose Forget in Settings → Memory."
            _forget(rows[0])
            return "Forgotten from shared memory. Existing chat transcripts and older backups remain separate."
        if pref.memory_enabled and pref.memory_suggestions:
            fact = parse_fact(text)
            if fact and m.PersonalMemory.objects.filter(user=command.user, status="suggested").count() < LIMIT:
                store(command.user, fact, source=message)
    return None
