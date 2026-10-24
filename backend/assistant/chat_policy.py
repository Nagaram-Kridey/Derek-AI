"""Bound interactive work without changing durable history or write approvals."""

import re


WEB_QUERY = re.compile(
    r"\b(latest|current|today|weather|forecast|news|recommend\w*|compare|comparison|best|search|research|"
    r"look up|internet|online|price\w*|availability)\b", re.I
)
ACTION_REQUEST = re.compile(
    r"\b(remind\w*|schedul\w*|calendar|event\w*|task\w*|workflow\w*|"
    r"automat\w*|report\w*|pdf|docx|file\w*|folder\w*|"
    r"every|daily|weekly|tomorrow|tonight|send|email|save|create|write|"
    r"update|change|delete|cancel|pause|resume|enable|disable|approve|reject|stop|book|buy|order|"
    r"pay|open|click|sign\s+in|log\s+in)\b", re.I
)


def direct_search_query(text):
    """Conservative read-only shortcut; ambiguous follow-ups use the model."""
    if ACTION_REQUEST.search(text) or not WEB_QUERY.search(text):
        return None
    if len(text.split()) < 4 or re.search(r"\b(it|that|those|them|these|this|above)\b", text, re.I):
        return None
    return text.strip()[:500]


def compact_history(conversation):
    # Exclude historical tool dumps. Readbacks remain in assistant messages;
    # confirmation identity/permission checks always use server database state.
    recent = list(conversation.messages.filter(role__in=["user", "assistant"])
                  .order_by("-created_at", "-id").values("role", "content", "metadata")[:40])
    rows = [{"role": row["role"], "content": row["content"]} for row in recent
            if not row["metadata"].get("personal_memory_command")
            and row["metadata"].get("handled_by") != "personal_memory"][:16]
    selected, budget = [], 20000
    for index, row in enumerate(rows):
        content = row["content"]
        if index == 0:
            # The current user request must never be silently cut.
            selected.append(row)
            budget -= len(content)
            continue
        if budget < 500:
            break
        limit = min(budget, 4000 if row["role"] == "user" else 3000)
        if len(content) > limit:
            marker = "\n[Earlier message abridged; ask for omitted details instead of inventing them.]\n"
            head = (limit - len(marker)) * 2 // 3
            content = content[:head] + marker + content[-(limit - len(marker) - head):]
        selected.append({"role": row["role"], "content": content})
        budget -= len(content)
    return selected[::-1]


DETAILS = {"auto", "brief", "balanced", "detailed"}
BRIEF = re.compile(r"\b(?:brief|briefly|concise|concisely|short answer|in short|tldr|tl;dr|one sentence)\b", re.I)
DETAILED = re.compile(r"\b(?:detailed|in detail|thorough|comprehensive|in.depth|step.by.step|expand|elaborate|lengthen)\b", re.I)


def answer_style(command):
    """Explicit request wins; accepted preferences and same-chat continuity follow."""
    from .capabilities import preferences
    from . import models as m
    text = command.input_text
    if BRIEF.search(text):
        return "brief"
    if DETAILED.search(text):
        return "detailed"
    pref = preferences(command.user)
    if pref.response_detail != "auto":
        return pref.response_detail
    if pref.memory_enabled:
        remembered = m.PersonalMemory.objects.filter(user=command.user, key="preference.reply_style", status="active").values_list("content", flat=True).first()
        if remembered:
            if BRIEF.search(remembered) or re.search(r"\bshort\b", remembered, re.I):
                return "brief"
            if DETAILED.search(remembered) or re.search(r"\blong\b", remembered, re.I):
                return "detailed"
    if re.search(r"^(?:and |also )?(?:what about|why|how|continue|go on|tell me more|explain (?:it|that|this)|can you explain)", text, re.I):
        previous = command.conversation.messages.filter(role="assistant").order_by("-created_at", "-id").values_list("metadata", flat=True).first()
        style = (previous or {}).get("answer_style")
        if style in {"balanced", "detailed"}:
            return style
    if re.search(r"\b(?:architecture|implementation plan|trade.?offs|design a|explain how|explain why|pros and cons)\b", text, re.I):
        return "detailed"
    return "balanced"


def reply_budget(command, *, synthesis=False, style=None):
    style = style or answer_style(command)
    budgets = {"brief": 384, "balanced": 1536, "detailed": 3072}
    if command.channel == "telegram":
        budgets = {"brief": 320, "balanced": 1024, "detailed": 2048}
    elif command.input_mode == "voice" and style != "detailed":
        budgets = {"brief": 320, "balanced": 512}
    # A concise spoken/text answer must not truncate structured workflow args.
    capacity = budgets[style]
    if not synthesis and ACTION_REQUEST.search(command.input_text):
        capacity = max(capacity, 2048)
    return capacity


def style_instruction(command, style):
    detail = {"brief": "Give a direct concise answer, normally 1–3 short paragraphs.",
              "balanced": "Answer fully enough to be useful. Explain the key reasoning, practical steps and material limits; use examples when they help. Do not force a tiny word limit or add filler.",
              "detailed": "Give a developed answer with clear sections, concrete steps/examples and relevant trade-offs. Address all parts of the request. Length should serve the question, without repetition."}[style]
    channel = (" Use short Telegram paragraphs, one idea per bubble; a complete answer may span multiple bubbles."
               if command.channel == "telegram" else "")
    if command.input_mode == "voice" and command.channel != "telegram":
        channel += " Put the spoken takeaway first; the full explanation can follow on screen. Never shorten an approval readback."
    return "Current answer detail: " + style + ". " + detail + channel + " The current request overrides any older length preference. Follow-ups should stay on the previous topic unless the user changes it; ask if the referent is missing."


def interactive_tools(command, tools):
    """Omit large write schemas from ordinary questions; never add permissions."""
    if ACTION_REQUEST.search(command.input_text) or re.search(r"\b(?:do it|do that|go ahead|proceed|make it|that one|enable|disable)\b", command.input_text, re.I):
        return tools
    reads = {"search_web", "list_tasks", "calendar_list_events", "inspect_workspace"}
    return [item for item in tools if item["name"] in reads]


def grounded_answer(text, sources):
    """Only retrieved URLs may be presented as evidence in a search synthesis."""
    from urllib.parse import urlsplit, urlunsplit
    def canonical(url):
        try:
            parts = urlsplit(url)
            return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
        except ValueError:
            return ""
    allowed = {canonical(item["url"]) for item in sources}
    removed = False
    def link(match):
        nonlocal removed
        if canonical(match[2]) in allowed:
            return match[0]
        removed = True
        return match[1] + " (link not retrieved)"
    text = re.sub(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", link, text)
    def plain(match):
        nonlocal removed
        url = match[0].rstrip(".,;:!?")
        if canonical(url) in allowed:
            return match[0]
        removed = True
        return "[link not retrieved]"
    text = re.sub(r"https?://[^\s<>\])]+", plain, text)
    return text, removed
