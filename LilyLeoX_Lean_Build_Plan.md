# Derek — Lean Build Plan & Phase Checklist
## Recommended Route Only: Method A (Django Monolith) + Method C (Agentic Graph as its Brain)

This supersedes the roadmap in Section 11 of `LilyLeoX_Architecture_Plan.md` with a **tighter, scope-locked** plan. Nothing here adds new work beyond what was already recommended — it locks the route to the single best path (A hosting C) and actively **cuts** anything that would make the build harder without a corresponding, necessary payoff.

---

## 1. Scope Lock

### IN — build this
| Area | What ships |
|---|---|
| Backend | One Django + DRF project (Method A), single deployable service |
| Brain | Gemini turn-based calls with function-calling; the research pipeline is a simple 4-step chain (Planner → Researcher → Verifier → Writer) run **in-process**, not a separate service |
| Scheduling | Celery + Redis + Celery Beat; one-off and recurring reminders/research jobs |
| Research | Web search (one provider) + academic search (Semantic Scholar **or** arXiv, not both) + a basic 2-source verification rule |
| Documents | `.docx` export via `python-docx`; PDF export via one simple conversion path |
| Voice | Push-to-talk (button/hotkey triggered) STT with local `faster-whisper`; TTS via Cartesia API |
| Reach | CLI, a simple React web dashboard, **and a Telegram bot** — this is your "on the phone" channel; no native app, no phone-call system |
| Auth | Single-user or basic JWT login — no OAuth, no third-party account linking |
| Deploy | One Docker image, one EC2 instance (or a single Render/Railway-style host), managed Postgres, managed Redis |
| Tests/CI | pytest + GitHub Actions on every push |

### OUT — explicitly not built (deferred indefinitely, not "phase 2")
These were all part of the full architecture plan but each one adds real engineering time without which the assistant is still fully usable end to end. Cutting them keeps total build time roughly 3–4 focused weeks instead of 2–3 months.

- ❌ Method B microservices, gRPC, Kafka/RabbitMQ, Kubernetes/Helm, EKS
- ❌ Native Android app (Kotlin/Flutter) — Telegram bot covers "usable on phone" instead
- ❌ Twilio real-time phone-call bridging (Media Streams + Gemini Live audio bridge)
- ❌ Custom/self-hosted voice cloning or TTS model fine-tuning — Cartesia hosted API only
- ❌ Always-on wake-word detection — push-to-talk only
- ❌ Critic-agent self-revision loop — the 4-step pipeline is Planner→Researcher→Verifier→Writer, full stop
- ❌ Model Context Protocol (MCP) tool exposure
- ❌ Multi-user org features, OAuth calendar/email linking
- ❌ Vector/long-term memory (Chroma) — conversation state stays in the DB/session only for v1

> If any of these are wanted later, they are additive, isolated features — none of them require re-architecting what you build now. That is exactly why cutting them here costs nothing later.

---

## 2. The Route, In One Paragraph

Everything lives in **one Django project**. A `Turn` API endpoint calls Gemini with a small set of function-declared tools (`run_deep_research`, `schedule_task`). `run_deep_research` is not a separate microservice — it's a plain Python function that runs the 4-step chain synchronously (or as a Celery task if it's slow) and returns a structured result, which another function turns into a `.docx`/`.pdf`. `schedule_task` writes a row to the database that Celery Beat polls and re-dispatches through the exact same code path later. Voice, web dashboard, and Telegram are three thin clients in front of this one API — none of them contain business logic.

---

## 3. The Process (repeat this loop for every phase below)

1. **Scaffold** — create the app/module and its empty files per the directory tree in the main architecture doc (Section 6.A / 10).
2. **Implement the narrowest version that satisfies the acceptance criteria** — no extra flexibility, no config options you don't need yet.
3. **Write the tests first or immediately after** — a phase is not "done" until its tests are green.
4. **Manual smoke test** — actually run the feature once by hand (CLI or Postman/HTTPie against the API).
5. **Commit and tag** (`git tag phaseN-done`) before starting the next phase.
6. **Do not start the next phase's code until the current phase's checklist is fully checked.** This is the single rule that keeps the project from sprawling.

---

## 4. Phase-by-Phase Checklist

### Phase 0 — Foundations
*Goal: a running Django project with CI, before any AI logic exists.*
- [ ] `django-admin startproject` + `apps/` layout from Section 6.A
- [ ] PostgreSQL configured locally via `docker-compose.yml` (db + redis only)
- [ ] `accounts` app: minimal `User` model + JWT login endpoint
- [ ] `.env.example` committed; secrets loaded via `django-environ` or similar
- [ ] `pytest` + `pytest-django` wired up with one trivial passing test
- [ ] GitHub Actions workflow: lint (`ruff`) + `pytest` on every push
- **Acceptance:** `pytest` passes locally and in CI; `python manage.py runserver` boots with no errors.
- **Est. effort:** 1–2 days.

### Phase 1 — LLM Orchestration Core
*Goal: one working `/v1/turn` endpoint that talks to Gemini with tools registered — no tools implemented yet, just routing.*
- [ ] `apps/orchestrator/gemini_client.py` (`GeminiClient.generate()` per the skeleton)
- [ ] `apps/orchestrator/tool_registry.py` with **only** `run_deep_research` and `schedule_task` declared (drop `file_or_system_action` — real-time environment interaction is the one FR that can be trimmed to "not needed for the core assistant experience" if time is tight; see note below)
- [ ] `apps/orchestrator/router.py` dispatch table, with both tools initially returning a hard-coded stub result
- [ ] `POST /v1/turn` DRF view: takes text, calls Gemini, dispatches any tool call, returns `reply_text`
- [ ] Unit tests with `GeminiClient` mocked (never hit the live API in CI)
- **Acceptance:** Sending `"remind me to drink water in 10 minutes"` returns a coherent reply and you can see in logs that `schedule_task` was the tool Gemini chose.
- **Est. effort:** 3–4 days.

> **Note on FR-8 (environment interaction):** if you want to keep it, the *simplest* legal version is a single `list_calendar_events`-style read-only action — skip file-write/shell actions entirely for v1. If effort is tight, cut this tool completely; nothing else in the plan depends on it.

### Phase 2 — Scheduler
*Goal: `schedule_task` is real, not a stub.*
- [ ] `ScheduledTask` model (per Section 6.A) + migration
- [ ] `nl_time_parser.py` using `dateparser` — support **one-off times and simple recurrence words only** (`daily`, `weekly`); skip custom cron-phrase parsing ("first Monday of the month") for v1
- [ ] Celery + Celery Beat wired into `docker-compose.yml`
- [ ] `tasks.run_due_task` Celery task that calls back into `router.dispatch`
- [ ] `freezegun`-based tests: create a task, advance time, assert it fires exactly once
- **Acceptance:** Create a reminder via `/v1/turn`, and it actually fires (visible in logs / a notification stub) at the right time in a test with frozen time.
- **Est. effort:** 2–3 days.

### Phase 3 — Deep Research Engine (the simplified 4-step chain)
*Goal: `run_deep_research` returns a real, verified, structured result.*
- [ ] `research/planner.py` — one Gemini call, decompose into 3–4 sub-questions (skip dynamic re-planning)
- [ ] `research/web_search.py` — **one** search provider (Tavily or SerpAPI; pick one, don't build a pluggable abstraction yet)
- [ ] `research/academic_search.py` — **one** academic source (Semantic Scholar API is enough; arXiv can wait)
- [ ] `research/verifier.py` — the ≥2-independent-domain rule only (no embedding-similarity relevance scoring yet — a simple domain/keyword overlap check is enough for v1)
- [ ] `research/writer.py` — combines findings into `executive_summary`, `key_findings`, `next_steps`, `sources`
- [ ] `research/pipeline.py` — chains the four steps as plain sequential function calls (no LangGraph dependency needed for a straight-line chain — only bring in LangGraph if/when you add branching/loops later)
- [ ] Integration test on one fixed topic with HTTP responses recorded via `vcrpy` (no live API calls in CI)
- **Acceptance:** Calling `run_deep_research("topic")` returns a dict with all four fields populated and every source in `sources` is a resolvable URL.
- **Est. effort:** 4–5 days.

### Phase 4 — Document Export
*Goal: the research result becomes a real file the user can open.*
- [ ] `documents/docx_builder.py` exactly per the skeleton (title → summary → findings → next steps → sources)
- [ ] PDF export via **one** method only — recommend converting the finished `.docx` with `soffice --headless --convert-to pdf` (LibreOffice) rather than building a parallel Jinja2/WeasyPrint HTML template; less code, guaranteed visual parity
- [ ] Files saved to a `media/reports/` folder and served via a signed/authenticated download URL
- [ ] Snapshot test: generated `.docx` has the expected headings via `python-docx` introspection
- **Acceptance:** After a research call, a downloadable `.docx` and `.pdf` exist on disk and are retrievable via the API.
- **Est. effort:** 1–2 days.

### Phase 5 — Voice Layer (push-to-talk, local CLI)
*Goal: the whole thing works by voice from a terminal, no wake word, no phone.*
- [ ] `voice/stt.py` — `faster-whisper` transcribes a recorded clip (press-to-record, not streaming)
- [ ] `voice/tts.py` — `CartesiaTTS.speak_stream()` per the skeleton, played through local speakers
- [ ] A small CLI loop: press Enter to record → STT → `/v1/turn` → TTS playback
- [ ] Contract tests using a couple of pre-recorded sample `.wav` files
- **Acceptance:** You can hold a full spoken conversation (ask it to schedule something, ask it to research something) from the terminal.
- **Est. effort:** 3 days.

### Phase 6 — Reach: Web Dashboard + Telegram (your "on the phone" channel)
*Goal: usable away from the laptop, without building a native app.*
- [ ] Minimal React dashboard: list scheduled tasks, list/download generated reports, a plain text chat box hitting `/v1/turn`
- [ ] Telegram bot (`python-telegram-bot`): text messages **and voice notes** (Telegram already gives you a `.ogg` voice note — pipe it through the same `stt.py`) both call `/v1/turn`; reports are sent back as native Telegram documents
- [ ] Telegram bot pushes reminder notifications directly (no FCM/native push setup needed — Telegram's own push notifications do this for free)
- **Acceptance:** From your phone's Telegram app, you can ask it to research something and receive the `.pdf` in the chat; a scheduled reminder arrives as a Telegram message at the right time.
- **Est. effort:** 3–4 days.

### Phase 7 — Hardening & Deploy
*Goal: it runs reliably somewhere other than your laptop.*
- [ ] Per-user daily token/request budget check in orchestrator middleware (simple Redis counter, not a full billing system)
- [ ] Secrets moved to environment variables on the host (AWS Secrets Manager only if you're already comfortable with it — plain env vars on the instance are acceptable for v1)
- [ ] Single Docker image; deploy to one EC2 instance (or Render/Railway) behind HTTPS
- [ ] Managed Postgres + Redis (RDS/ElastiCache, or the host's managed equivalents)
- [ ] 48-hour soak test of the scheduler (not the full 30-day version from the main doc — enough to catch obvious double-fire/missed-run bugs)
- [ ] README with setup + architecture summary for the GitHub repo
- **Acceptance:** The full flow (voice or Telegram → schedule/research → report delivered) works against the deployed instance, not just `localhost`.
- **Est. effort:** 3–4 days.

---

## 5. Global Definition of Done (applies to every phase)

- [ ] Feature works when exercised manually, not just in a mocked test
- [ ] `pytest` suite for the phase is green in CI
- [ ] No hard-coded secrets or API keys committed
- [ ] The phase's checklist above is 100% checked before moving on

**Total estimated effort:** ~20–25 focused working days (roughly 4–5 weeks part-time), versus 2–3 months for the full architecture document's complete scope.

---

## 6. Deferred / "Later, If Ever" List (kept separate on purpose)

Not part of this plan, not scheduled, not blocking anything above. Revisit only after Phase 7 ships and you actually want one of these for a specific reason (interview prep, real usage need, etc.):

- Native Android app
- Twilio real-time phone-call channel (Gemini Live audio bridge)
- Custom/fine-tuned voice model
- Always-on wake word
- Method B microservices/Kubernetes migration
- Multi-source academic search, cron-phrase scheduling, embedding-based verification, long-term vector memory, MCP exposure, Critic-agent revision loop

Keeping this list visible (rather than silently forgetting these ideas) is what makes it safe to cut them now without feeling like scope was lost.
