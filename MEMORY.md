# Derek shared long-term memory

Updated: **2026-10-20 · Asia/Kolkata**

## Use it

Open **Settings → Memory** in Derek, or say/type these in the normal web, Telegram or online voice conversation:

- `Remember that my preferred programming language is Python`
- `Remember Project: Derek is my personal assistant project`
- `Remember Reply preference: concise explanations with concrete examples`
- `What do you remember about me?` or `/memories`
- `Forget Project` or `Forget Reply preference` using the exact saved label

These are examples, not details automatically saved about you. Saving/listing/forgetting through these explicit commands is handled locally, without a model call. Repeating the same fact does not add duplicate entries. Reusing a named label corrects that saved detail; standard profile labels have stable identities so a name/project correction replaces the previous accepted value.

Memory is shared by owner account, not limited to one conversation. Starting a new chat does not clear accepted memories. Telegram and online voice retain their usual sender/authentication rules. **Private desktop chat is excluded:** its transcript is not scanned, shared or sent to an online model.

## Review and control

Settings → Memory provides:

- Add a labeled fact, edit its detail or mark it broadly useful across conversations.
- Accept or discard suggestions. Only accepted details enter model context.
- Pause memory retrieval/saving, or separately disable automatic suggestions.
- Scan up to 500 recent user messages from normal Derek chats for suggestions.
- Forget a specific fact. Stale edits cannot silently overwrite a newer change.

Ordinary statements such as “I work as …”, “My project is …” and clear preferences produce **suggestions**, not silently accepted facts. The historical scan is local and conservative: it recognizes explicit remember requests and a small set of first-person profile/preference statements. It does not infer a lasting interest from every question or create arbitrary summaries of old conversations. The initial scan found zero unambiguous suggestions in the available recent history.

Credential/key/recovery-code patterns are rejected from memory. A rejected detail can still remain in the original chat transcript if you typed it into chat; this feature does not sanitize every existing message. Do not submit secrets as memories.

## Fast recall

The implementation adds **no embedding service and no additional model-generation call** to an ordinary reply:

1. Accepted facts have normalized, indexed search terms.
2. The current question selects keyword matches plus broadly useful/pinned profile facts.
3. At most five facts enter the prompt, with a combined serialized-fact budget of 1,800 characters.
4. The normal model request receives these facts alongside its existing recent-history window.

The lookup is scoped to the authenticated owner, with at most 200 accepted and 200 suggested records per owner. It performs a bounded local database query; it does not scan lifetime chat history per turn. There is no stale application memory cache to invalidate after a correction.

This is lexical retrieval with pinned profile facts, not full semantic recall. It can miss paraphrases that share no indexed terms. Pin broadly useful context, use descriptive labels, or restate a detail when necessary. Model latency and concurrent database activity still vary; no absolute reply-time guarantee is made.

## Trust and privacy

Recalled facts are sent as **untrusted personal data**, not system instructions, tool permissions or confirmation. Current user corrections take precedence. Derek's existing tool validation, allowed folders/domains and exact action approvals remain in Python. Shared memory cannot authorize a Calendar write, start a workflow, run shell commands or approve itself.

The response records only the IDs of recalled memories in `memory_ids_used`; normal routing/instruction metadata remains available. The selected online model provider receives any recalled fact included in its request. “Local memory storage” does not mean inference is private/local. Private desktop mode remains a separate local-only path.

Facts and their term index live in the normal `backend/db.sqlite3` database. That live database is not encrypted. The owner export includes memory records and settings; backups of the normal database include memory at the snapshot date.

Forgetting deletes the fact and indexed terms. A content fingerprint prevents a later history scan from suggesting the exact forgotten/corrected fact again; it stores no original fact text. An explicit new Remember request can intentionally save a forgotten fact again. Edited or forgotten transcript text may still be present in original chats, provider records or older backups. Pause/forget controls affect future assembled requests, not context already sent to a provider.

Deleting a source conversation also deletes memories copied directly from its messages. Manually added/corrected facts are independent. Deleting all normal assistant history clears all shared memories and suppression fingerprints. Remember/list/forget command acknowledgements are excluded from the recent model-history window so those management replies do not act as a hidden second memory store. Other ordinary recent messages can still contain the same detail; start a fresh chat or delete that conversation if you also want that transcript context removed.

## Interfaces and implementation

| Interface | Purpose |
|---|---|
| `GET /v1/memories/` | Owner's settings and accepted/suggested details |
| `POST /v1/memories/` | Save an explicit labeled detail |
| `PATCH /v1/memories/` | Pause retrieval or suggestions |
| `PATCH /v1/memories/{id}/` | Edit/accept/pin with the current version |
| `DELETE /v1/memories/{id}/` | Forget the exact current version |
| `POST /v1/memories/scan/` | Local bounded scan of prior normal user messages |

Code: `backend/assistant/memory.py`, `memory_views.py`, migration `0010_personal_memory.py`, `web_dashboard/src/Memory.tsx`. Shared instruction version is **2026-10-20.5**. Memory is not a model-exposed executable tool; explicit controls are server handlers. `/memory on|off` and `/suggestions on|off` change the same normal-chat settings; accepted reply-style memory can guide adaptive answer detail.

## Implementation evidence and remaining acceptance

- Migration 0010 applied during managed startup; runtime backend and interactive worker reported ready.
- Python compilation, selected Ruff checks, Django system check and migration consistency passed.
- TypeScript/Vite production build passed; Settings contains the memory controls.
- Authenticated memory settings returned HTTP 200, with retrieval/suggestions enabled and no stored facts.
- Local prior-history scan completed with zero suggestions; no model call or private-history import.
- No new automated tests, model recall probe, Telegram test message or live voice interaction was run for this feature. Earlier 124-Python/8-dashboard results predate memory and do not validate it. Cross-channel recall, corrections, owner isolation, pause/forget behavior and latency still need explicit acceptance.
