# Derek — Implementation Checklist

Updated: **2026-10-19 · Asia/Kolkata**

## Current status

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

## Remaining implementation and acceptance

### Work that can continue without new account credentials

- [ ] Complete live local acceptance when requested: voice arming/mute/interruption, exact reminder confirmation, recovery, incoming Telegram and approved file/browser workflows.
- [x] Run the expanded automated regression suite on explicit request: 116 Python and 8 dashboard tests pass; production-code line coverage is 49%. Live acceptance remains separate.
- [ ] Measure general Gemini/Ollama/voice latency on this laptop; CPU-only inference can be slow. The historical Ollama greeting took 69 seconds; new quick built-ins are not a general model benchmark.
- [ ] Add model token streaming and a server audio session transport; speech currently starts after text generation completes.
- [ ] Verify lock/sleep/reboot, crash recovery and a complete backup restore. Current backups are local DB snapshots, not an off-device recovery system; report files and private-chat DB are separate.
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

- **2026-10-19 — publication verified:** Published the implementation as `6f79d45`, then fixed the clean-runner development dependency as `8017226`. Confirmed remote `main` matches the code commit and all four [GitHub CI jobs](https://github.com/Nagaram-Kridey/Derek-AI/actions/runs/39164712178) passed. Read-only local smoke checks returned 200 for the workspace/health/built assets, 401 for an unauthenticated API request, and 200 for the existing owner session with private/no-store caching. The 121-file staged credential/local-artifact scan had no findings. This documentation-only follow-up records the result without rerunning unchanged application code.

- **2026-10-19 — verification/publication request:** Added isolated test settings, blocked unmocked network/account access and native credential changes during tests, updated earlier tests for the reviewed-action/strict-sender contracts, and expanded regression coverage to 116 Python plus 8 dashboard tests. Fixed cancellation before provider setup, transaction-aware connection cleanup, API path normalization checks and Docker exclusions for local state/database journals. TypeScript/Vite, Ruff, Django/schema, pip/npm, Terraform and Compose checks passed. Added Linux/PostgreSQL and Windows CI coverage. Full results and remaining boundaries: [RELEASE_CHECK.md](RELEASE_CHECK.md).

- **2026-10-19:** Resumed implementation. Restored the stopped local runtime, corrected Windows credential blob encoding, improved existing voice-client credential refresh and authentication errors, made workflow cancellation/edits transactional and research cancellation follow its parent workflow, hardened partial Telegram delivery, and added Windows owned-process containment plus stop/restart availability after preparation failures. Current services report fresh ready states. The overdue authorized research run completed at 01:51 IST; the PDF delivery API confirmed success at 01:52 IST. The next regular trigger is 11 AM today. No crash injection, automated tests, microphone interaction or new test messages were performed.

- **2026-10-18:** Implemented the local tray/runtime, native voice window/hotkey, private local chat/voice, Windows voice credentials, expanded dashboard, editable schedules, report progress/cancellation, local Telegram receiver/buttons, report-file delivery queue, snapshots and recovery hardening. Prepared production dashboard assets; Python/static/schema checks passed. One actual overdue research occurrence completed after a safe research-only retry for cold-model startup. Reviewed its four-page PDF. Runtime reload succeeded, migrations through 0009 are applied, and encrypted database snapshot evidence was recorded. No new automated tests, paid inference probes, phone changes, cloud provisioning or GitHub push.

Earlier dated work, historical test/CI results, published commit IDs and the separate launch-film draft are preserved in [IMPLEMENTATION_HISTORY.md](IMPLEMENTATION_HISTORY.md).
