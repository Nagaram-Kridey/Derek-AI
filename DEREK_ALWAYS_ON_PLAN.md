# Derek - Always-On Personal Assistant Plan

Prepared: 2026-10-15 (Asia/Kolkata)

Updated: 2026-10-18 (Asia/Kolkata)

Status: **Local desktop runtime, dashboard and native voice window implemented; live acceptance remains pending.** The local adaptation uses a Python tray supervisor, built React app in an installed browser's app window, loopback Waitress, SQLite-backed worker lanes and an approved-chat Telegram poller. It starts without Docker, Redis or Vite. Windows sign-in startup, Ctrl+Alt+Space, native credential storage, private Ollama chat/voice, report reading/progress, command recovery and editable routines are implemented. A real daily research run completed on 2026-10-18 and its four-page PDF was visually reviewed; evidence labels remain unverified where corroboration is missing. See [LOCAL_APP.md](LOCAL_APP.md), [PRIVATE_CHAT.md](PRIVATE_CHAT.md) and [VOICE_SETUP.md](VOICE_SETUP.md). This does not establish live voice, incoming Telegram, sleep/reboot or confirmation acceptance. Model token streaming, cloud authority, signed standalone packaging, wake word and telephone provisioning remain planned. Progress and exact operational evidence are tracked in [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md).

## 1. Goal and debate decisions

Make Derek available through an installed Windows app, the web dashboard, Telegram and, after an eligibility/cost gate, an ordinary Indian phone number. One assistant owns the tasks and permissions; each channel has its own response format.

Confirmed preferences: Gemini first; Ollama available as an explicit local option; cloud access while the laptop sleeps; both a wake word and push-to-talk hotkey; a +91 inbound number; a low-cost pilot with paid phone provisioning deferred.

Phone update: Kridey has a spare Samsung Galaxy A32 4G with a usable Airtel SIM (carrier corrected on 2026-10-15). Preferred route is carrier forwarding from that existing number to an eligible Indian voice gateway, subject to Airtel plan/destination support, provider approval and costs. No forwarding has been changed. See [PHONE_SETUP.md](PHONE_SETUP.md).

The original architecture and lean documents are reference material. This request expands their earlier scope to include an installed app, wake word and telephone access. It does not require implementing every architecture or instruction in those documents.

### Debate outcome

Three agents reviewed the actual repository and challenged each other's proposals: laptop architect, channel architect and red team. Their final follow-up settled the voice pipeline and privacy boundary.

| Topic debated | Decision and reason |
|---|---|
| Entire assistant on laptop versus cloud authority | Cloud owns conversations, commands, schedules and approvals. Laptop runs microphone, browser, approved files and optional local inference. This supports remote access while the laptop sleeps. |
| Browser-only app versus installed Windows app | Tauri 2 with bundled React assets and a packaged Python companion. Tray controls, global hotkey and reliable device access justify the native component. Keep the web dashboard too. |
| Gemini versus Ollama versus custom LLM | Gemini for normal online interactions. Explicit private desktop Ollama mode. Future custom model connects through the same adapter; training stays in its separate project. |
| Native Gemini Live versus separate speech stages | First release uses speech detection -> Whisper transcription -> Gemini text/tool proposals -> streamed Cartesia speech. Server-generated action readbacks make confirmation and result wording predictable. Native Live is a later adapter. |
| Runtime agent swarm versus shared tools | Keep the existing research chain and typed tools. The debate team is a design method; a continuously running group of agents is unnecessary for ordinary commands. |

### Starting point

Django/DRF, React, research/reports, reminders, reviewed workflows, a paired browser/file companion, Gemini/Ollama adapters and basic voice components exist. They require further live acceptance. Incoming Telegram has no registered public webhook; Calendar is not connected; production is not deployed.

At the original review on 2026-10-15, voice waited for a whole recording, full model reply and complete WAV, and channel context/recovery were incomplete. The implementation now persists channel conversations and command/action/delivery records, streams Cartesia PCM, adds local VAD and provides a native tray/voice window. Text generation still finishes before speech begins; token streaming, wake word and a phone gateway remain gaps. The historical CPU Ollama greeting took 69 seconds; no new general-inference latency target has been established. Exact read-only greetings/help/time/status/tasks have a separate local fast path. Report evidence and proposed business benefits still require scrutiny.

## 2. Implementation design

### Shared core and feature understanding

All channels follow the same flow:

```text
Authenticated channel -> persistent session -> durable command
    -> available capabilities + model proposal
    -> validation / required confirmation -> action execution
    -> saved result -> channel formatter -> independent delivery
```

- Build one capability registry from the typed tool contracts. Include description, examples, argument schema, execution location, allowed channels, required connector, approval rule and current availability. Report ready, needs setup, offline, permission blocked or temporarily unavailable with a reason.
- Generate the model's allowed tools and a dashboard Features page from this registry. Recheck authorization and availability at execution. A configured credential alone does not mean a connector works.
- Keep persistent conversations per desktop thread, voice session and approved Telegram private chat. `/new` resets Telegram context. Share owner preferences and task records across channels; transfer a specific conversation through an explicit handoff rather than mixing every transcript.
- Store Command, ActionProposal, ActionExecution and Delivery records independently. Deduplicate incoming source events and individual action steps. Serialize commands within a conversation and version shared task/event updates.
- Render scheduled, queued, completed, failed and uncertain outcomes from server state. The model can explain results but cannot decide whether an action succeeded. Delivery failure never restarts an already committed action.
- Reuse stable caller-generated Calendar event IDs. Use Calendar ETags/If-Match for updates; a stale version requires refetch and renewed confirmation. An uncertain remote outcome is reconciled before retrying. [Calendar version handling](https://developers.google.com/workspace/calendar/api/guides/version-resources)
- Add reminder list/update/pause tools and direct owned-calendar create/update proposals. Existing reviewed workflows retain their scopes, version snapshots, approval digests, device leases and execution journal. Spoken scheduling must no longer call the immediate-write path before confirmation.

### Public interfaces

Keep `POST /v1/turn` and its existing response fields for compatibility. Route it through the shared command core; upgraded clients supply a stable request ID for safe retries.

| Interface | Purpose |
|---|---|
| `POST /v1/commands` | Accept text/transcript, request ID, conversation ID and selected model profile; promptly return command ID and current state. |
| `GET /v1/commands/{id}` and `/events` | Fetch the saved outcome or stream ordered text/progress/action/artifact events; support reconnect using event sequence IDs. |
| `POST /v1/action-proposals/{id}/confirm` | Confirm the exact current revision; reject expired, replaced or already consumed confirmations. Cancellation uses the same proposal lifecycle. |
| `GET /v1/capabilities` | Explain current features and setup/offline restrictions to the UI and model. |
| `GET/PATCH /v1/preferences` | Set voice, channel verbosity and available model profiles. Credentials never appear in these responses. |
| `POST /v1/voice/sessions` plus authenticated WSS | Stream speech/control events using a short-lived session ticket; support stop, interruption and reconnect. |

Server authentication determines owner, channel and permissions; client-supplied channel labels cannot grant access. Existing Telegram and device endpoints become adapters to the same core. The phone adapter adds provider ingress and a separate authenticated media socket. Add Django ASGI/Channels and Uvicorn for HTTP/event/audio streaming; the current deployment is WSGI-only.

### Models, voice and Windows app

- Add model profiles for interactive chat, background research and private local chat. Keep model IDs configurable and initially reuse the configured Gemini text model after checking access/quota. Pin provider/privacy mode for an active session; a switch starts an explicit handoff or new conversation.
- Extend adapters with streamed text, typed tool proposals, structured output, cancellation, readiness, timings and usage. Retain the existing 100 model-call/day and 300,000 input-character/day defaults initially; account for actual retries and reserve interactive capacity before admitting research. Add output-token, audio-duration and per-job limits.
- Online desktop voice: local wake word/VAD -> persistent `base.en` CPU int8 faster-whisper -> cloud command core/Gemini -> streaming Cartesia -> interruptible playback. Speech detection defines utterance boundaries; this is an utterance-based pipeline, not a claim that Whisper becomes a native streaming recognizer. [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Cartesia streaming examples](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/examples.py)
- Use local Porcupine detection for "Hey Derek", with a configurable global hotkey initially `Ctrl+Alt+Space`. Custom wake words require a Picovoice account, AccessKey and Windows keyword asset; hotkey input remains available without them. [Porcupine setup](https://picovoice.ai/docs/quick-start/porcupine-python/)
- Audio states: idle, listening, transcribing, thinking, speaking, muted and unavailable. Display transcript and clear listening indicator; provide immediate mute/stop. Default to a 30-second idle timeout and five-minute active voice session, with a continuation control. Idle wake-word audio stays on the laptop and is not saved or uploaded.
- Speak short replies as sentences become available. For a mutation, speak an immutable target/date/time/timezone readback, then collect a fresh confirmation bound to its revision. Expire proposals after two minutes. Ambiguous AM/PM, dates or event targets require a question.
- Interrupting clears audio and obsolete confirmation input. Before commit, cancel the proposal; after commit, stop speaking and report the saved result. Never treat "stop" as an automatic undo.
- Package React locally in Tauri and Python with PyInstaller in one compatible release. Start at user logon, minimize to tray, supervise one companion instance, reconnect with backoff and pause microphone/browser interaction when Windows locks. Provide a signed installer/update path with rollback and narrow, typed IPC. Windows services cannot directly provide interactive desktop access. [Tauri sidecars](https://tauri.app/develop/sidecar/), [Windows interactive services](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services)
- Store laptop credentials with Windows credential protection. Browser profile and website sessions remain local. The current local app keeps Django/Waitress and database-backed workers on the PC, with no Redis, Celery worker or running Vite server. A future cloud-client package can remove the local application server after cloud cutover; signed Tauri/PyInstaller packaging remains a later release choice.
- **Private local chat:** explicitly select Whisper -> Ollama -> an installed Windows speech voice, with separate local history and no cloud synchronization. This pilot mode supports chat and local drafts; cloud account tools, schedules and workflow mutations are unavailable. Reconnection never submits drafts automatically. If Windows speech is unavailable, retain text. [Installed Windows voices](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.getinstalledvoices?view=netframework-4.8)
- Defer cloud-directed Ollama jobs and native Gemini Live. Gemini Live supports real-time audio, transcripts, tools and interruption, but needs session reconnection and the same deterministic action boundary. Neither local inference nor a future custom model bypasses permissions or confirmation. [Live API](https://ai.google.dev/gemini-api/docs/live-api), [Live sessions](https://ai.google.dev/gemini-api/docs/live-api/session-management)

### Responses by channel

| Channel | Default experience |
|---|---|
| Desktop/web text | Readable detail, streaming answer, sources, progress, action cards and report links. |
| Desktop voice | One or two short sentences; one clarification at a time. Detailed answer remains on screen. |
| Telegram text | One to three short, meaningful messages in order; typing status and a More button for detail. Attach reports separately. |
| Telegram voice note | Transcribe and use the same session; reply in text by default. `/voice on` enables short voice-note replies. |
| Telephone | Brief reminders and owned-calendar read/create/update conversations. Research can be queued and delivered to Telegram/dashboard after the call. |

Telegram must validate the webhook secret, private chat type, approved chat ID and approved sender ID. Persist delivery message IDs, apply at most one message/second per chat and respect `retry_after`. A transport timeout with unknown send outcome becomes needs-attention rather than a blind duplicate. [Telegram limits](https://core.telegram.org/bots/faq)

### Cloud availability and phone adapter

- Pilot: one x86 AWS EC2 instance in Mumbai, initially two vCPUs/four GiB RAM, running Caddy HTTPS, Django ASGI, PostgreSQL, Redis, one Beat and bounded worker processes through Docker Compose. Keep RDS/ElastiCache as a later hosting option; the existing managed-services Terraform is not the default low-cost deployment.
- Separate interactive command, due-task, research and delivery workers. Phone media uses an asynchronous gateway and a warm cloud transcription process, not a Celery audio stream or the laptop microphone service. Limit research concurrency to one; pause admission of heavy research during a call and enforce memory/CPU limits. Enable phone only after a realistic capacity/latency check on the chosen host; resizing needs a revised cost review.
- Cloud reminders, Calendar, Telegram and phone continue while the laptop sleeps. Browser/file work shows waiting for device, uses its existing deadline, and revalidates after reconnect. Require renewed review when the approved target/state has changed. The system cannot execute PC-only work on a powered-off laptop.
- Encrypt storage, keep daily encrypted PostgreSQL backups off-host with seven daily and four weekly recovery points, store reports privately in S3 and preserve recoverable encryption keys. Add an actual restore exercise, external uptime monitoring and alerts for scheduler lag, worker failure, expired jobs and provider failures. One host remains a single point of failure.
- Prepare an **Exotel AgentStream Voicebot** adapter for the +91 pilot. It supports bidirectional PCM, DTMF, playback markers and clearing; resample its audio explicitly for STT/TTS. [Exotel protocol](https://developer.exotel.com/docs/agentstream/websocket-protocol)
- **Provisioning gate:** confirm personal-use eligibility, +91 inbound-number availability, KYC documents, streaming enablement and total recurring/usage/tax charges before buying anything. Exotel's guide refers to company documentation, so an individual account cannot be assumed eligible. [Exotel onboarding](https://support.exotel.com/support/solutions/articles/3000132268-quick-guide-to-get-started-with-exotel-streaming-services)
- Do not substitute an international number automatically. Twilio's India guidelines list ordinary domestic inbound as N/A and toll-free separately; a suitable local number is not established by its general calling API. If +91 eligibility fails, leave telephone disabled and retain Telegram/desktop access. [Twilio India](https://www.twilio.com/en-us/guidelines/in/voice)
- Enroll the owner number through the authenticated dashboard and use a rate-limited six-digit DTMF PIN. Caller ID is only an additional check. Allow three failed PIN attempts before a 15-minute lockout; suppress PIN digits from model input, transcripts and logs. Verify provider ingress and issue one-use media tickets bound to the call/account/destination.
- Initial phone limits: one simultaneous call, five minutes/call and 30 minutes/month. Number provisioning and calling remain disabled until an approved provider quote and monthly application budget are recorded. Usage caps stop new application work; they do not cancel fixed hosting/number rental or guarantee an exact external bill.
- Phone cannot approve workflow activation, purchases, payments, security changes or permanent deletion. These need trusted dashboard review under the existing approval rules. No Calendar delete tool or arbitrary shell access is added. No outbound calling in this pilot.
- Disconnect before confirmation means no action; disconnect after commit preserves the result and queues a Telegram summary. Derek recording is off by default and raw audio is ephemeral. Provider retention remains subject to the chosen provider settings/terms; do not promise provider-side zero retention.

## 3. Delivery sequence

| Phase | Deliverables | Exit condition |
|---|---|---|
| A. Shared assistant core | Capability registry/Features UI; profiles; persistent sessions; command/proposal/action/delivery records; mutation confirmations; compatible turn API and command events. | Follow-ups preserve context; retries create one action; unavailable features are explained accurately. |
| B. Speech prototype | Reuse existing Whisper/Gemini/Cartesia components; add VAD, warm models, streamed speech, stop/barge-in and exact spoken action readback. Prototype through current development setup before installer work. | Simple voice conversations and ambiguous scheduling pass; latency is measured by stage; interruption cannot authorize an action. |
| C. Cloud and Telegram | Add ASGI deployment, low-cost Compose/Terraform option, production HTTPS/secrets, independent worker lanes, budgets, backups and persistent Telegram text/voice formatting. Connect Calendar. | Laptop-off reminder/Calendar/Telegram flow works; restore succeeds; research does not delay reminders. |
| D. Installed Windows app | Tauri tray app, bundled companion, wake word/hotkey, microphone controls, private local chat, device reconnect, startup/restart and signed release/update handling. | Reboot/logon, lock/mute, sleep/resume, offline mode and incompatible-update rollback behave correctly without development terminals. |
| E. Telephone pilot | Provider eligibility/cost review first; then provider adapter, authenticated inbound calls, warm cloud STT, PIN, audio cancellation, confirmations and Telegram summaries. | One real +91 inbound call can schedule/update a task while the laptop is off, within the agreed caps. If eligibility fails, this phase stays blocked without blocking A-D. |

Cloud cutover must preserve histories, workflow IDs, schedule/occurrence records and report references. Freeze mutations for the final copy, stop the local scheduler before enabling the cloud scheduler, and reconcile the last executed occurrence. Re-pair the desktop against production and reconnect OAuth using its production redirect; generate production credentials rather than exposing/copying development secrets. Rollback also uses exactly one authoritative scheduler.

Update the checklist per phase using Proposed, Implemented and Verified distinctly. Record measured results and unresolved problems. Do not mark the current daily report automation or new channels production-ready just because code exists.

## 4. Probable issues and acceptance scenarios

| Probable issue | Required handling / acceptance scenario |
|---|---|
| CPU-only local LLM is slow | Keep Gemini online default; show local-mode latency honestly. Do not claim instant voice from the current 69-second result. Future custom model passes the same tool/schema/privacy/latency evaluations. |
| Duplicate action after webhook retry, worker crash or lost reply | Replay one Telegram event and command repeatedly; crash after Calendar commit but before delivery. One saved action/event exists and delivery resumes independently. Uncertain outcomes reconcile before retry. |
| Misheard time or stale confirmation | "Move tomorrow's meeting to seven" asks which meeting and AM/PM. Interrupting readback invalidates an earlier yes. Only the latest exact proposal can commit. |
| Concurrent phone and Telegram edits | Conditional Calendar update detects a changed ETag and asks for a refreshed confirmation; no silent overwrite. |
| Research blocks real-time work | Run a report while receiving commands and dispatching a reminder. Queue isolation plus resource limits maintain responsiveness; reject new heavy work when capacity is exhausted. |
| Laptop sleeps or internet fails | Cloud tasks still work with the laptop off. File/browser work waits and expires safely. Private chat does not upload history or activate cloud tools after reconnect. |
| Wake-word false positives, feedback and accidental listening | Local wake test, echo handling, immediate mute, lock and capture indicators. Idle audio never leaves the laptop. A wake event alone cannot execute a write. |
| False capability or completion claims | Revoke Calendar, disconnect the device and exhaust quota. Features UI/model immediately report blocked reasons; queued jobs are never described as completed. |
| Prompt injection in pages/research | Retrieved content cannot grant permissions, activate workflows, broaden approved paths/domains or confirm a proposal. Verify the existing boundaries still hold. |
| Hallucinated project research | Preserve independent-domain verification and unverified labels; do not invent market figures. Five ideas/top two must retain evidence status and bounded MVP assumptions. |
| Phone number unavailable or charges excessive | No paid provisioning before documented eligibility/quote/budget. Simulate minute caps and provider failure; disable calling cleanly while other channels continue. |
| VM outage, damaged update or lost data | Restore encrypted backup on a clean host; verify one scheduler. Reject incompatible shell/sidecar updates and recover the last working release. |

Performance release targets, measured on an awake laptop and warm Gemini path with a representative network: command acknowledgement p95 under one second; first text p95 under 2.5 seconds; first meaningful spoken answer p95 under four seconds after utterance end for simple requests. A listening chime is not a meaningful answer. Action completion time is measured separately. Test idle tray CPU below two percent excluding inference and wake detection on at least 90 percent of a small recorded sample, with fewer than one false wake per eight hours of representative ambient audio. These are targets, not measured guarantees.

No new tests or live provider actions were run to produce this plan. The scenarios above are the intended acceptance work for implementation.

## 5. What Kridey needs to do and defaults

1. **Online model:** ensure Gemini has usable quota/billing for the configured model and agree to the application limits. Gemini availability was previously affected by quota; the existing key alone does not resolve that.
2. **Hosting:** provide AWS deployment access through normal credentials, a domain/DNS setup and an approved monthly hosting/model budget before resources are created. The plan contains no guaranteed price quote.
3. **Accounts:** complete Google Calendar OAuth consent when Calendar is needed. The Telegram bot already exists and the local polling receiver is running; incoming chat/voice and confirmation acceptance remain pending. A public HTTPS webhook is needed for the later cloud route, with a deliberate single-receiver cutover.
4. **Desktop:** approve microphone/autostart, create the Picovoice AccessKey/custom Windows wake-word asset if wake-word mode is wanted immediately, choose a voice, and approve file/site scopes. Complete website sign-ins manually in the dedicated browser profile.
5. **Phone later:** obtain confirmation that the personal-use case qualifies for a +91 number, supply the provider's required KYC, review the actual quote, enroll the permitted caller number and choose the DTMF PIN in the app. No account purchase is required merely to implement phases A-D.
6. **Live acceptance:** participate in microphone, pronunciation/time clarification, lock/sleep/reconnect and eventually a short phone-call check. Keep the current laptop services awake for the existing daily research workflow until cloud cutover is completed.

Defaults: single owner Kridey; English first; Asia/Kolkata; existing research/report workflow retained; concise speech; Telegram text replies unless voice is enabled; raw audio not retained by Derek; normal online history remains exportable/deletable under existing controls; private local history stays on the PC and never auto-syncs. Custom LLM training, native Android, arbitrary shell execution, outbound calls, runtime agent swarms and managed high-availability infrastructure stay outside this expansion's pilot.
