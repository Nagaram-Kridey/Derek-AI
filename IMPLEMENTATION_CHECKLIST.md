# Derek — Implementation Checklist

Updated: **2026-10-24 · Asia/Kolkata**

### Resumed verification — 2026-10-23

- [x] Existing Python regression suite: 152 passed, 1 opt-in real Chrome test skipped. Dashboard: 8 passed.
- [x] Added and passed 3 focused regressions: complete detailed Telegram text in bubbles of at most 500 characters, adaptive reply budgets with sufficient voice action capacity, and tool filtering that preserves workflow controls.
- [x] Enabled Windows sign-in startup through the existing desktop installer; installer confirmed the Derek shortcut and startup registration.
- [ ] Resolve supervisor `needs_attention` status before claiming live acceptance. Workers, companion and Telegram were reporting fresh activity; backend and Ollama readiness records were stale.
- [ ] Live site/Telegram context, detailed model responses and confirmed control acceptance remain pending.
- [ ] Local desktop automatic sign-in and scoped screen/mouse implementation remain pending. Existing protected voice credentials do not establish automatic dashboard sign-in.

## Current status

### Next desktop batch — local sign-in and observation, 2026-10-24

- [x] Add a 45-second single-use local launch handoff bound to the saved owner token; revoke/rotation, exact host/origin, redirect and replay checks preserve ordinary site authentication.
- [x] Desktop browser consumes/removes the fragment code and shares its one exchange across React effects; normal site access still uses login. Initial owner sign-in remains necessary when no Windows credential exists.
- [x] Add Settings/tray launch of an off-by-default two-minute per-app native UI Automation preview. Bind consent to window/process/executable/start time; omit password-marked controls; exclude elevated and known sensitive/browser/terminal apps.
- [x] Keep preview results in native memory with bounded metadata, a cancellable child, background IPC reception and generation-bound callbacks. No screenshots, mouse input, model/Telegram screen transport or executable agent tool is enabled.
- [x] Live local launch/exchange HTTP 200; returned existing session matched, replay HTTP 401, unauthenticated ordinary status HTTP 401. Credential values were not printed.
- [x] Migration consistency check, selected Ruff checks, dashboard tests and production build passed. Expanded Python suite initially passed 208 tests with one optional browser test skipped; final post-review suite is recorded below when complete.
- [x] Final post-review verification: **214 Python tests passed / 1 optional browser test skipped**; **9 dashboard tests plus actual Settings rendering checks passed**. Added regressions for stale callbacks, spawn failure, nonblocking IPC and consent expiry during reader cleanup.
- [ ] Accept automatic sign-in through the actual desktop window and local per-app preview through explicit consent. Both roadmap items remain in progress for this acceptance; mouse/action stage remains planned.

Usage: [DESKTOP_ACCESS_SETUP.md](DESKTOP_ACCESS_SETUP.md). Review log: [DESKTOP_BATCH_2026-10-24.md](DESKTOP_BATCH_2026-10-24.md).

### Resumed runtime/recovery verification — 2026-10-24

- [x] Local service restored; health returned HTTP 200. Prior simultaneous heartbeat cessation does not establish a specific failure cause.
- [x] Pre-migration regressions verify encrypted backup/restore before schema preparation, key failure before database-mode changes, and no redundant backup when no migration is pending.
- [x] Stale supervisor controls now report unknown availability. Fixed startup-button null handling; actual Settings rendering is checked in the dashboard test command.
- [x] Real isolated Windows process fixture passed crash/restart and captured descendant termination checks. Production workers were not interrupted.
- [x] **191 Python tests passed / 1 optional browser test skipped**; **8 dashboard tests plus Settings rendering regression passed**. Selected Ruff checks passed.
- [x] Production build and managed reload completed; all configured services returned fresh ready status and supervisor running. Authenticated status/roadmap HTTP 200; evidence saved to both existing roadmap blocks.
- [ ] Real sign-in/reboot/sleep, extended soak, off-device recovery and actual disaster cutover remain pending. Runtime and recovery groups remain in progress.

### Runtime and recovery session — 2026-10-24, in progress

Closing check at **12:30 IST**: the authorized work cutoff has passed and the checkpoint automation has been deleted. Recorded work does not demonstrate two hours of continuous implementation or overnight monitoring. Local runtime records were stale and the health endpoint refused connection; restart/availability acceptance remains pending. See the session log for actual evidence.

- [x] Selected two existing in-progress items: local runtime/startup reliability and backup/restore recovery. Timestamped scope/review log: [WORK_SESSION_2026-10-24.md](WORK_SESSION_2026-10-24.md).
- [x] Add status-file retries, optional-component fault isolation, sanitized diagnostics, attachment-failure rollback, initial service retry, backup retry and bounded shutdown.
- [x] Add encrypted database + referenced-report archives with atomic publication, authenticated metadata/chunks, bounded file validation and isolated restore verification. Stop creating new plaintext pre-migration snapshots; existing backups are preserved.
- [x] Real installation archive passed isolated restore verification: database plus eight report files. No live database replacement, private-chat import or restored job execution.
- [x] First full regression run: 179 passed / 1 opt-in browser test skipped. Four additional reviewer-driven regressions then passed in the 24-test focused runtime/recovery suite. Final full-suite rerun remains pending during this session.
- [x] Dashboard build and selected Ruff checks passed. Settings now exposes supervisor degradation and verified recovery scope.
- [x] Full suite after attachment rollback fixes: **184 passed / 1 optional browser test skipped**. Subsequent bounded ZIP-directory preflight passed focused recovery checks; final checkpoint should rerun the complete suite after all remaining edits.
- [ ] Complete independent post-fix review, monitored runtime checks and final session report. Real reboot/sleep and disaster cutover remain separate acceptance items.

Operational guide: [RECOVERY_SETUP.md](RECOVERY_SETUP.md). The two-hour work window ends at **03:19 IST**; ten-minute checkpoints should pause at that cutoff.

### Product roadmap and mobile access — 2026-10-23

- [x] Consolidate 35 feature groups across original scope, later requests, future suggestions and difficult extensions in [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). Preserve historical records separately.
- [x] Generate [visual roadmap](docs/roadmap.svg) and add a responsive Roadmap page to the local dashboard.
- [x] Persist owner roadmap blocks with versioned saves, dependency validation, evidence requirements, planning inclusion toggles, priority/status filters, duplication, test plans, prompt generation, JSON export and print/PDF.
- [x] Four focused roadmap API tests passed; TypeScript/Vite builds and selected Ruff checks passed. Local authenticated endpoint returned 200 with 35 blocks after restart/migration.
- [x] Prepare and publish a separate static-only `roadmap-pages` branch and configure GitHub Pages. Mobile drafts stay in the current browser; export/copy prompts to transfer. Only the sanitized starting catalog is published, not the owner database.
- [x] Public page and catalog returned HTTP 200 with 35 blocks. Seven focused roadmap/response tests passed after final backend changes.
- [ ] Browser visual acceptance: local browser automation is disabled in Codex Work settings. Build/API checks passed; actual mobile/browser interaction remains to be accepted.
- [ ] Shared remote editing, live laptop status, automated isolated test execution and real capability switches remain separate work. Planning toggles and test queues do not execute actions.

Roadmap mobile URL: https://nagaram-kridey.github.io/Derek-AI/ . Local URL: http://127.0.0.1:8000/#roadmap . See [mobile hosting details](ROADMAP_MOBILE.md).

### New implementation — adaptive model use and shared controls

- [x] Persist a shared answer-detail preference (`auto`, `brief`, `balanced`, `detailed`), available through Features and `/style` in normal online conversations; explicit requests override it.
- [x] Increase bounded answer capacity instead of forcing web replies into 512 tokens. Keep Telegram bubbles concise while allowing complete detailed multi-bubble replies. Let Ollama honor the requested larger chat budget.
- [x] Retain up to 16 recent user/assistant messages with a 20,000-character budget, abridging older long messages instead of dropping all older turns. Preserve the current request and owner-scoped accepted memory; keep private history separate.
- [x] Use shared prompt version **2026-10-20.5** for topic continuity, precision and uncertainty. Remove source URLs invented during search synthesis; this is link validation, not proof that every factual claim is supported.
- [x] Omit large write schemas on ordinary questions, record provider-call latency on saved replies, and poll fast online voice responses sooner with bounded backoff.
- [x] Add model-independent `/controls`, inspection tools and exact shared confirmation operations for workflow edits/enable/pause/run, global pause/resume, run/report cancellation, sensitive-step review/decisions and Telegram PDF copies. Dashboard operations reuse the same handlers. Workflow edits save disabled and cancel pending runs. Exact names resolve only when unique; stale targets/checkpoints require fresh review.
- [x] Add shared `/memory on|off`, `/suggestions on|off` and `/model configured|gemini` controls; current conversations retain their pinned model.
- [x] Add migration `0011_response_detail`, update owner export and document the control matrix in [MODEL_USAGE_AND_CONTROLS.md](MODEL_USAGE_AND_CONTROLS.md).
- [x] Python compilation, selected Ruff checks, Django system/migration consistency checks and dashboard production build passed for this increment.
- [x] Managed restart applied the preference migration after its pre-migration snapshot. Backend, workers, companion, Ollama and Telegram returned fresh ready status. Read-only authenticated API checks exposed the new shared controls and the default `auto` preference; no new task/workflow/action was activated during rollout.
- [ ] Acceptance/regression coverage for these new model/control changes: adaptive depth, multi-turn relevance, stale/replayed cross-channel controls, full Telegram delivery and global pause/resume. The **153 Python / 8 dashboard** result below predates this increment; no new automated tests or live model/action tests were run for it.
- [ ] Account/device setup, bulk export/delete and memory editor/pinning remain dashboard controls. Large complete reviews can require the dashboard. Phone transport and general Windows screen control remain planned.

### Latest check — voice scheduling and browser flexibility, 2026-10-20

- [x] Running-app check through `VoiceSession` → real companion client → command queue → exact proposal → voice confirmation → persisted reminder. Recognized speech and completed playback were simulated; no microphone/speaker acceptance is claimed.
- [x] Verified no reminder existed before confirmation, one task existed after confirmation, and repeated confirmation returned the same task without duplication.
- [x] Preserved test reminder **review Derek voice scheduling verification**, ID `ab73a271-23ec-4aa2-b692-cf1fe6600732`, scheduled **2026-10-21 11:00 Asia/Kolkata**, then **paused** it to prevent test delivery. Inspect it in Automations/Activity. No test Telegram message was sent.
- [x] Added 28 regressions covering spoken reminder routing, ambiguous requests, past-time failure, exact confirmation persistence, safe browser drafts, semantic targets, bounded waits/scrolling, duplicate targets and scope checks.
- [x] Added an opt-in real installed Chrome regression with intercepted fixture pages and a fresh context. Navigation, delayed content, label fill/select, exact role click, scrolling and readback passed; payment approval, wrong page, duplicate targets and MFA paused without action.
- [x] Full companion browser runner completed read-only public HTTPS navigation/read using a temporary profile and domain/DNS filtering. Signed-in account workflows remain a separate acceptance item.
- [x] Browser contracts now support exact role/name, label, text, placeholder and test-ID targets, existing CSS selectors, body-default reads, bounded waits and target scrolling. Max 30 actions; mutation page/risk checks, manual login, domain scopes and journaling remain enforced.
- [x] Shared prompt version **2026-10-20.4** describes these actions and explicitly marks general desktop control unavailable. The capability catalog now lists Windows screen control as planned.
- [x] **153 Python tests passed**, including opt-in real Chrome acceptance; **8 dashboard tests passed**. Selected Ruff checks and the dashboard TypeScript/Vite production build passed. Normal CI skips the real Chrome test unless explicitly opted in.
- [x] Django system/schema checks and `git diff --check` passed. Gracefully restarted Derek; backend, workers, companion, Ollama and Telegram returned fresh ready/polling status. Authenticated API verified the new browser schema and planned desktop capability, and the saved test reminder remained paused after restart.
- [ ] Complete a real microphone/readback/confirmation check with the laptop's audio devices. The saved-task/database path above passed independently of audio devices.
- [ ] Implement the scoped Windows observation adapter, followed by reviewed desktop actions and a bounded visual agent loop: [SCREEN_CONTROL_PLAN.md](SCREEN_CONTROL_PLAN.md). No generic screen-input service is enabled yet.

Repeat isolated browser acceptance with `$env:DEREK_BROWSER_ACCEPTANCE='1'` followed by `.\.venv\Scripts\python.exe -m pytest companion/tests/test_browser_live.py -ra`. It uses an installed Chrome and intercepted fixture pages, never the owner's profile. Local live evidence is retained in ignored `.companion/setup/voice-scheduling-result.json`, `browser-acceptance-result.json` and `public-browser-result.json`.

The local app, dashboard, native voice window and private local chat are implemented. This is a source installation with a desktop shortcut and Windows tray, not a signed standalone installer. It runs on this laptop without Docker, Redis or a Vite development server. The latest source changes passed compilation/static/schema checks. The runtime was started again on 2026-10-19; all services are online, the overdue authorized research run completed, and Telegram confirmed its PDF delivery. Crash/reboot and live channel acceptance remain pending.

**Open:** the **Derek** desktop shortcut, `Derek.vbs`, or [the local workspace](http://127.0.0.1:8000/). Sign in as **Kridey** with your existing password. Startup at Windows sign-in is enabled and can be changed in Settings. Closing the workspace leaves the tray running. The laptop must stay awake for local schedules and Telegram access.

**Evidence rules:** checked implementation items mean the code exists. The dated evidence below distinguishes builds, startup observations and actual completed work from live acceptance. On the subsequent explicit request to check, test and publish, the automated suite was expanded: 116 Python tests and 8 dashboard tests pass. Production-code line coverage is 49%, so this is not exhaustive acceptance. Static, schema, dependency and infrastructure checks passed. The expansion is published on `main`; GitHub CI passed on Windows, Linux/PostgreSQL, the dashboard and Terraform. Publication evidence is recorded below.

Guides: [Local app](LOCAL_APP.md) · [Voice](VOICE_SETUP.md) · [Private local chat](PRIVATE_CHAT.md) · [Automations](AUTOMATION_SETUP.md) · [Phone](PHONE_SETUP.md) · [Architecture/debate](DEREK_ALWAYS_ON_PLAN.md). Earlier records and publication evidence are preserved in [IMPLEMENTATION_HISTORY.md](IMPLEMENTATION_HISTORY.md).

## Completed implementation — local product session

### Startup and recovery

- [x] Serve the built React dashboard and authenticated API together on loopback port 8000 with Waitress.
- [x] Add tray controls, a current-user desktop shortcut, a separate Edge/Chrome dashboard app window and Windows sign-in startup controls.
- [x] Supervise separate conversation, research, delivery, scheduler, paired companion and optional Telegram/Ollama processes.
- [x] Use durable database queues locally, without Docker/Redis; retain cloud/Celery as a separate mode and refuse overlapping runtimes.
- [x] Add a single launcher lock, process heartbeats, bounded restart backoff, bounded service logs and graceful drain/restart controls.
- [x] Use SQLite WAL and short serialized write transactions. Back up before migrations and on startup; add a daily managed database snapshot, encrypted when a valid existing encryption key is configured.
- [x] Protect assistant source, state and browser-profile folders from file workflows. Ignore SQLite database, WAL, shared-memory and journal files in Git.
- [x] Keep API errors sanitized, private responses uncached, and dashboard fonts/assets local. Provider keys are still in the ignored environment configuration.

### Everyday dashboard

- [x] Today: upcoming routines, recent updates, counts and service status.
- [x] Chat: persistent conversation/model profile, Markdown, citations, conversation search and exact confirmation cards.
- [x] Recover unresolved commands by saved request ID; retrieve without resubmission, stop unfinished replies and inspect saved action outcomes.
- [x] Command history: filter/search, saved requests/replies, event timeline and current proposals.
- [x] Create/edit reminders and research schedules, choose weekdays, review the schedule and inspect occurrence history.
- [x] Workflow templates for check-ins, websites, local notes and research, with explicit permission/trigger review before activation.
- [x] Reports: stage progress, cancellation, searchable reading, shortlist/ranking reasons, production-feature plans, per-finding source/excerpt inspection, evidence labels and PDF/DOCX downloads.
- [x] Extend the owner data export with message metadata, command events, workflow runs, schedule occurrences, notifications and preferences; exclude provider/authentication credentials and separate attachments.
- [x] Activity/notifications: search audit events and mark updates read without deleting the record.
- [x] Retry-safe create forms with explicit request IDs and a 30-day replay window; changed values cannot reuse an unresolved saved request.
- [x] Optional remembered browser sign-in; local sign-in refreshes online voice access in Windows Credential Manager. Sign-out revokes online access.

### Voice and model use

- [x] Native voice window: **Ctrl+Alt+Space** opens/focuses; Listen explicitly arms capture. Space starts/finishes/interrupts; Esc mutes.
- [x] Warm local Whisper, local speech-end detection, bounded sessions, streamed Cartesia PCM, interruption and saved-request recovery.
- [x] Exact spoken reminder/Calendar readback and confirmation binding; expired/replaced/unheard proposals cannot be approved with an unbound yes.
- [x] Windows-lock pause and separate shared audio-session lock; microphone is closed on window open, idle, mute and exit.
- [x] Explicit private Ollama text/voice mode with separate PC-only history, export/delete controls and an installed Windows voice. No cloud sync, account tools or internet tools in that mode.
- [x] Keep Gemini/current-installation profiles pinned per conversation; no silent provider fallback. Background research retains the installation provider, currently Ollama/qwen3:4b.
- [x] Add exact read-only greeting, help, time, date, status and task-list answers without model inference. General model generation is still not token-streamed.

### Telegram and delivery

- [x] Run one approved-private-chat long poller in local mode without public HTTPS. Persist accepted updates/offsets and reject other private senders or groups.
- [x] Respect receiver conflicts and polling retry delays; never delete/replace a registered webhook automatically.
- [x] Keep persistent channel context and concise ordered text replies with durable delivery states.
- [x] Add signed buttons for the exact owner/proposal/revision. A bare Telegram yes cannot authorize an arbitrary action.
- [x] Separate new report PDF delivery from research, with queued/sent/needs-attention state and an explicitly confirmed extra-copy action.
- [x] Preserve uncertain/partial send outcomes for inspection instead of automatically replaying accepted actions/messages.

## Operational evidence — this session

| Observation | Result / boundary |
|---|---|
| Python compilation and selected Ruff error/undefined/unused checks | Passed for backend, companion and desktop modules |
| Django system check in managed local configuration | No issues; schema consistency check found no missing migration changes |
| Dashboard TypeScript/Vite production build | Passed; built assets prepared for the local server |
| Desktop shortcut and Windows Run entry | Installed for the current Windows user; reboot/logon behavior is not yet accepted |
| Managed runtime startup | On 2026-10-19, backend, four lanes, companion, Ollama and Telegram reported fresh ready/working heartbeats. Ctrl+Alt+Space is registered and sign-in startup is enabled. Windows process ownership and CLI recovery for failed startup are implemented; crash/reboot acceptance is pending |
| Local backup / voice credentials | Encrypted daily database snapshot saved; existing owner voice access stored and read through Windows Credential Manager after correcting its Unicode blob format |
| Local Telegram receiver | Bot accepted polling, no webhook was replaced; incoming user conversation/voice acceptance remains pending |
| Actual daily research catch-up | One overdue occurrence dispatched. The initial cold-model metadata timeout was corrected; the same research-only run was safely retried once and completed at 01:31 IST on 2026-10-18 |
| Generated report | Report `60af6d03-ad3f-4f7b-a9d4-7ff2a14759d8`: five proposals, two shortlisted plans, PDF/DOCX files, six findings. No findings met verification criteria; labels remain unverified |
| Report layout/delivery evidence | All four PDF pages visually reviewed; report-ready notification status is sent. Recipient confirmation of this PDF and DOCX visual review remain pending |
| Automated regression | 116 Python tests and 8 dashboard tests pass, including exact confirmations, cancellation, request/form retries, worker lanes, signed Telegram buttons, simulated voice controls/VAD, private chat and local-model boundaries. Test accounts/database/media are isolated; live services are not called |
| Live acceptance | Microphone/playback, real Calendar/Telegram conversations, lock/sleep/reboot and full browser/file workflow acceptance remain open |
| Follow-up report, 2026-10-19 | Report `fa72bc44-2f70-4cda-96ac-078ada8c0520` completed: five proposals, two shortlisted plans, six unverified findings, PDF/DOCX files. Five PDF pages visually reviewed. The new file-delivery queue resumed after the graceful restart and Telegram returned success; recipient confirmation is separate |
| Publication / hosting / phone | Published to `Nagaram-Kridey/Derek-AI` on `main`; verified code commit `8017226`. All four [GitHub CI jobs](https://github.com/Nagaram-Kridey/Derek-AI/actions/runs/39164712178) passed. No AWS provisioning, phone call or forwarding change |

## Daily enterprise software and AI research

- [x] Reviewed workflow **Daily enterprise software and AI project ideas** remains enabled.
- [x] Trigger: **every day at 11:00 AM Asia/Kolkata**. Delivery follows research completion.
- [x] Five proposals with target users, problem hypotheses, MVP, evidence and heuristic ranking; two receive detailed implementation plans.
- [x] Execution-date context and seven-day recent-title checks. Repetition and market demand are not guaranteed by automated research.
- [x] Two actual overdue scheduled occurrences, on 2026-10-18 and 2026-10-19, completed through the local worker pipeline. It was a catch-up run, not a punctual 11 AM observation.
- [ ] Observe the next punctual run: **2026-10-19 at 11:00 AM**, with the laptop awake.
- [ ] Inspect the new DOCX visually; the existing renderer needs LibreOffice. PDF layout was reviewed.
- [ ] Improve independent-source breadth and manually assess proposal usefulness; all current findings are explicitly unverified.

Latest completed report: `fa72bc44-2f70-4cda-96ac-078ada8c0520`. Telegram confirmed PDF delivery.

Workflow ID: `a7401ae6-1640-4864-a8fc-bc9e38c42dd4`. Do not create a duplicate routine. To change the trigger, edit the existing workflow, review and enable it again.

## Shared long-term memory — 2026-10-20

- [x] Add owner-scoped personal facts, indexed search terms, versioned edits and forgotten-fact suppression; migration 0010 applied.
- [x] Share accepted details across normal web, Telegram and online voice conversations, independent of the selected model. Private desktop chat is excluded.
- [x] Add local Remember, /memories and exact-label Forget commands, with no model call. Ordinary clear profile/preference statements and prior-history findings are reviewable suggestions.
- [x] Retrieve at most five relevant accepted facts within 1,800 serialized characters. Bound each owner's store to 200 accepted/200 suggested facts; no embeddings, extra inference or lifetime-history scan on the reply path.
- [x] Add Settings → Memory: add, accept, edit, pin, forget, pause and local previous-chat scan. Export includes memories/settings; deleting all history clears memory; source-chat deletion removes directly derived facts.
- [x] Keep recalled facts untrusted and separate from tool permissions. Reject common credential patterns; preserve existing confirmation gates. Remember/list/forget acknowledgements do not re-enter recent model history.
- [x] Python compilation/Ruff, Django/schema consistency and dashboard production build passed. Runtime started with memory enabled; authenticated settings HTTP 200. Initial local scan of up to 500 prior user messages found zero unambiguous suggestions and made no model calls.
- [ ] Accept live cross-channel recall/correction, owner isolation, forgetting/pausing and latency. No new automated tests or model/Telegram/voice probes were run for this feature; the previous 124/8 baseline predates memory.

Guide: [MEMORY.md](MEMORY.md). Accepted details may be included in the configured online provider's context. Forgetting does not erase original transcripts, provider records or older backups.

## Active model roles and routing checks — 2026-10-20

- [x] Use the owner's updated port-3001 FreeLLMAPI URL/key. Authenticated model listing and hosted inference passed; credential values were not displayed.
- [x] Route chat, tool selection, search synthesis, Telegram and online voice through `auto:fast`; route schema-based research planning, verification, project proposals, shortlisting and summary selection through `auto:smart`. Private desktop chat remains local Ollama.
- [x] Request `reasoning_effort=none` to avoid hidden reasoning exhausting concise reply budgets. Preserve requested/served model and router-provider identifiers in saved answers and model-routing audit events.
- [x] Live checks: chat 3.0 seconds; public search 8.1 seconds with six citations; reminder proposal 3.0 seconds, cancelled without creating a task; Telegram-style preview three bubbles of 171/195/186 characters, not sent. Structured research planning returned valid JSON through the smart route. Individual samples are not a latency guarantee.
- [x] Expanded regression: **124 Python tests and eight dashboard tests passed** after routing/template changes; TypeScript/Vite production build passed. These results supersede the earlier pre-change 116/8 baseline for current local source.
- [x] Document actual model roles, recent context limits, communication, chat/database locations, privacy and backup boundaries in [DEREK_MODEL_AND_DATA_FLOW.md](DEREK_MODEL_AND_DATA_FLOW.md). Display chat/research profiles in Settings → Connections.
- [ ] Accept incoming Telegram delivery, full report generation, live microphone/speech and overnight/crash/reboot operation with the new router. Port 3001 is owner-managed and must remain running; the separate portable port-31415 setup is not the active route.

## Response speed and optional FreeLLMAPI — 2026-10-20

- [x] Route clear current-information/recommendation questions directly to public search before inference; synthesize with one model call. Action/report requests and ambiguous pronoun follow-ups retain model/tool routing.
- [x] Bound interactive history to eight recent user/assistant messages and 12,000 characters; omit historical tool dumps. The current user request is retained intact. Older context remains in the saved conversation but is not all sent to the model.
- [x] Compact runtime capability status context. Telegram prompts target 40–90 words; generation budgets are 320 tokens for ordinary replies and 256 for search synthesis, retaining 512 for detailed/action requests. Existing 500-character bubbles and complete approval readbacks remain.
- [x] Implement FreeLLMAPI provider selection, authenticated OpenAI-compatible inference, registered-tool validation, structured research requests, cancellation, usage/health records and truthful provider/privacy status.
- [x] Install/open the official FreeLLMAPI v0.16.5 portable Windows app on loopback port 31415. Copy its existing unified key through the app to ignored `.env`; authenticated model listing returned HTTP 200. Connect the existing local Ollama `qwen3:4b` endpoint and select FreeLLMAPI `auto:fast` in Derek. No cloud-provider keys/account purchases were added. See [setup/model comparison](FREELLMAPI_SETUP.md).
- [x] Python compilation, selected Ruff checks and the TypeScript/Vite dashboard build passed. Local startup reports backend, interactive worker, Ollama and Telegram ready. No live inference was performed.
- [ ] Accept the new routing/context behavior, tool/schema compatibility, live Telegram output and actual before/after latency. The previously published 116/8 test results predate these changes; no new automated tests or inference benchmarks were run.
- [x] Configure the local router and unified key, select Current installation for owner conversations, and add optional launch of the known portable router when Derek starts. Reload `.env` on managed restarts so provider/key changes apply. Router crash/reboot acceptance remains pending.
- [x] Centralize versioned base/channel/task instructions for chat, search synthesis, research planning, verification, ideas, shortlisting and report summary in [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md). Model-independent Python contracts/approval checks remain authoritative.
- [ ] Add approved hosted provider keys if faster hosted inference is wanted, then accept tools, JSON reports and latency for those models. The current router route still uses the CPU-bound local model.
- [ ] Compare smaller local `qwen3:1.7b` and optionally `qwen3.5:2b` against the current model for speed and task correctness before changing the local model.

## Remaining implementation and acceptance

### Work that can continue without new account credentials

- [ ] Complete live local acceptance when requested: voice arming/mute/interruption, exact reminder confirmation, recovery, incoming Telegram and approved file/browser workflows.
- [x] Run the expanded automated regression suite on explicit request: 116 Python and 8 dashboard tests pass; production-code line coverage is 49%. Live acceptance remains separate.
- [ ] Measure general Gemini/Ollama/voice latency on this laptop; CPU-only inference can be slow. The historical Ollama greeting took 69 seconds; new quick built-ins are not a general model benchmark.
- [ ] Add model token streaming and a server audio session transport; speech currently starts after text generation completes.
- [ ] Verify lock/sleep/reboot and actual disaster-recovery cutover. New encrypted archives include the normal database and referenced reports, with isolated restore verification; private chat and off-device recovery remain separate.
- [ ] Package a signed standalone Windows installer/update path. Current source installation depends on this project folder and virtual environment remaining in place.
- [ ] Add an optional wake word with explicit microphone controls and measured false-wake behavior.

### Requires your setup or decision later

- [ ] **Google Calendar:** supply OAuth client configuration and complete account consent; then accept live read/create/update behavior. Calendar deletion is not exposed.
- [ ] **Browser/file tasks:** approve actual folders/sites and complete manual sign-in/MFA/CAPTCHA in Derek's separate profile. Pairing and prior YouTube navigation already have evidence.
- [ ] **Cloud while laptop sleeps:** hosting/model budget, AWS access, domain/HTTPS and production consent, then one-scheduler/one-Telegram-receiver cutover, backup and monitoring acceptance.
- [ ] **Phone:** confirm Airtel forwarding/destination support, gateway eligibility and total cost for the Samsung Galaxy A32 4G number before provisioning. No phone route is configured.
- [x] **GitHub publication:** published on 2026-10-19. Local tests passed; code commit `8017226` passed Windows, Linux/PostgreSQL, dashboard and infrastructure [CI](https://github.com/Nagaram-Kridey/Derek-AI/actions/runs/39164712178). A documentation-only follow-up records this result.

## What you need to do now

**No new API key is required for these local improvements.** Open the desktop shortcut and use the existing owner sign-in. Keep the laptop awake for the 11 AM routine. Use Features to choose a model for a new conversation; existing conversations keep their profile. Open voice and choose Listen only when ready to speak. Settings can pause automations or disable Windows sign-in startup.

Cloud access while asleep, Calendar consent, manual website sign-in and the Airtel phone route still need your participation. Purchases, payments, account-security changes and permanent deletion keep their approval gates. The local app exposes no arbitrary shell or script execution.

## Progress log

- **2026-10-20 — voice scheduling correction:** Inspected actual failed voice turns: browser drafts used incorrect action fields, and a model claimed a reminder was set without calling a tool. Added conservative local schedule routing, typed workflow-step schemas, actionable validation errors, failed status for all-failed tool turns and a guard against the identified unsupported completion claims. Extended affirmative voice vocabulary while retaining complete-readback/expiry binding. Browser routines remain disabled drafts requiring Automations review. Compilation/Ruff checks passed; no new automated tests, model/microphone probes, confirmed task or workflow activation. See [VOICE_SETUP.md](VOICE_SETUP.md).

- **2026-10-20 — shared long-term memory implemented:** Added local bounded fact retrieval, explicit memory commands, conservative reviewable suggestions, versioned owner controls, correction/forget suppression, export/delete integration and Settings UI. Applied migration 0010 and restarted the local runtime. Compilation/static/schema/build checks passed; initial prior-chat scan returned zero suggestions. No extra inference, private-history import, automated tests or live channel probes were performed. Details and acceptance boundaries: [MEMORY.md](MEMORY.md).

- **2026-10-20 — hosted route accepted for sampled tasks:** Port 3001 accepted the owner-updated key. Fixed hidden-reasoning budget exhaustion, recorded actual routed models, added separate fast/smart task roles, and confirmed live chat/search/proposal/Telegram-style/structured-plan samples. No Telegram test message or confirmed write was sent; zero test reminder tasks exist. All 124 Python and eight dashboard tests and the dashboard build passed. Added the model/context/storage guide.

- **2026-10-20 — router connected and task templates:** Installed/opened the official portable FreeLLMAPI v0.16.5 app. Copied its existing unified key through the visible app into ignored `.env` without displaying the value. Added the existing local Ollama endpoint in its dashboard; authenticated available-model listing returned HTTP 200. Selected FreeLLMAPI `auto:fast` and the owner's Current installation profile. After restart, authenticated Derek status returned HTTP 200 with provider `freellmapi`; backend, interactive worker, Ollama and Telegram report ready. Centralized versioned task/channel templates, added optional local-router startup, and fixed `.env` reload across managed restarts. No upstream cloud keys, paid inference, automated tests or latency benchmark were run.

- **2026-10-20 — latency and FreeLLMAPI:** Implemented conservative direct-search routing, bounded recent context, smaller Telegram generation budgets and an optional FreeLLMAPI adapter. Added provider status/privacy reporting, configuration examples and setup/model research notes. Compilation and Ruff checks passed. The unified router key is absent, so Ollama remains selected and live FreeLLMAPI acceptance is pending. No automated tests, paid inference, account creation or Telegram test messages were run.

- **2026-10-19 — conversational web answers and Telegram:** Added explicit current-information/recommendation search instructions and a read-only fallback when the model omits a search tool call. Search-only results receive a tool-free answer-synthesis step with source links; failed synthesis retains search evidence. Telegram uses paragraph bubbles capped at 500 characters, normally up to six, with full longer answers saved in the dashboard. Proposal readbacks are never truncated; confirmation buttons remain on the final bubble. Existing durable ordering/retry controls remain. Python compilation and selected Ruff checks passed. Automated tests, live search quality and Telegram recipient acceptance were not run for this change.

- **2026-10-19 — Ollama selected:** Set the installation provider to Ollama (`qwen3:4b`), changed Kridey's default conversation profile to Current installation, and switched the one existing Gemini conversation to that profile at the owner's request. Saved command history is unchanged. No model inference or regression tests were run for this configuration change.

- **2026-10-19 — publication verified:** Published the implementation as `6f79d45`, then fixed the clean-runner development dependency as `8017226`. Confirmed remote `main` matches the code commit and all four [GitHub CI jobs](https://github.com/Nagaram-Kridey/Derek-AI/actions/runs/39164712178) passed. Read-only local smoke checks returned 200 for the workspace/health/built assets, 401 for an unauthenticated API request, and 200 for the existing owner session with private/no-store caching. The 121-file staged credential/local-artifact scan had no findings. This documentation-only follow-up records the result without rerunning unchanged application code.

- **2026-10-19 — verification/publication request:** Added isolated test settings, blocked unmocked network/account access and native credential changes during tests, updated earlier tests for the reviewed-action/strict-sender contracts, and expanded regression coverage to 116 Python plus 8 dashboard tests. Fixed cancellation before provider setup, transaction-aware connection cleanup, API path normalization checks and Docker exclusions for local state/database journals. TypeScript/Vite, Ruff, Django/schema, pip/npm, Terraform and Compose checks passed. Added Linux/PostgreSQL and Windows CI coverage. Full results and remaining boundaries: [RELEASE_CHECK.md](RELEASE_CHECK.md).

- **2026-10-19:** Resumed implementation. Restored the stopped local runtime, corrected Windows credential blob encoding, improved existing voice-client credential refresh and authentication errors, made workflow cancellation/edits transactional and research cancellation follow its parent workflow, hardened partial Telegram delivery, and added Windows owned-process containment plus stop/restart availability after preparation failures. Current services report fresh ready states. The overdue authorized research run completed at 01:51 IST; the PDF delivery API confirmed success at 01:52 IST. The next regular trigger is 11 AM today. No crash injection, automated tests, microphone interaction or new test messages were performed.

- **2026-10-18:** Implemented the local tray/runtime, native voice window/hotkey, private local chat/voice, Windows voice credentials, expanded dashboard, editable schedules, report progress/cancellation, local Telegram receiver/buttons, report-file delivery queue, snapshots and recovery hardening. Prepared production dashboard assets; Python/static/schema checks passed. One actual overdue research occurrence completed after a safe research-only retry for cold-model startup. Reviewed its four-page PDF. Runtime reload succeeded, migrations through 0009 are applied, and encrypted database snapshot evidence was recorded. No new automated tests, paid inference probes, phone changes, cloud provisioning or GitHub push.

Earlier dated work, historical test/CI results, published commit IDs and the separate launch-film draft are preserved in [IMPLEMENTATION_HISTORY.md](IMPLEMENTATION_HISTORY.md).

Final closure verification: **185 Python tests passed, 1 opt-in browser test skipped**. This verifies isolated regressions, not live runtime availability.
