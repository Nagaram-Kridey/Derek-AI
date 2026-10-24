# Derek

Source repository: [Nagaram-Kridey/Derek-AI](https://github.com/Nagaram-Kridey/Derek-AI).

A personal assistant with a Django API, React dashboard, durable schedules and a Windows companion for approved file and browser workflows. Choose Gemini, local Ollama or the configured FreeLLMAPI router. Google Calendar, Telegram and Cartesia are optional connected services. [Model roles and data flow](DEREK_MODEL_AND_DATA_FLOW.md) explains context and storage; [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) records current implementation and verification status.

## Use the local Windows app

On this laptop, open the **Derek** desktop shortcut or double-click `Derek.vbs`. The app lives at [127.0.0.1:8000](http://127.0.0.1:8000/) and stays running in the Windows tray after its window closes. Startup at Windows sign-in is enabled for Kridey's installation and can be changed in Settings or the tray menu. The laptop must remain awake for local routines and Telegram access.

The managed local runtime serves the built dashboard with Waitress and runs separate database-backed conversation, research, delivery and scheduling processes. **It needs no Docker, Redis or running Vite server.** Do not run a second Celery/development stack against the same database. Full setup, startup/recovery commands and backup scope: [LOCAL_APP.md](LOCAL_APP.md).

- **Today:** next routines, unread updates and current service health.
- **Chat and Command history:** persistent conversations, explicit model choice, saved outcomes, stop/retrieve controls and exact confirmation cards.
- **Shared memory:** say “Remember label: detail” across normal web, Telegram or voice chats. Settings → Memory provides review, corrections, pinning, pause and forget controls. [Memory guide](MEMORY.md).
- **Answer detail and shared controls:** use `/style auto|brief|balanced|detailed` and `/controls` in web chat or Telegram. Workflow/run/report controls use exact confirmations and the same operation handlers as the dashboard. [Usage and control matrix](MODEL_USAGE_AND_CONTROLS.md).
- **Automations:** reviewed workflows, editable reminders, selected weekdays and execution history.
- **Reports:** progress, cancellation, readable evidence/project shortlists, PDF/DOCX downloads and explicit Telegram delivery copies.
- **Voice:** Ctrl+Alt+Space opens the native voice window; choose Listen to arm the microphone. Settings also opens online or private voice. See [VOICE_SETUP.md](VOICE_SETUP.md).
- **Private local chat:** tray action or `python -m companion private`; isolated Ollama history, no account tools or cloud synchronization. See [PRIVATE_CHAT.md](PRIVATE_CHAT.md).
- **Telegram:** the local approved-private-chat poller receives messages without public HTTPS when no webhook is registered. It never removes an existing webhook.

The application code and shortcut are installed locally; a signed standalone installer, wake word, cloud availability while the laptop sleeps and phone calling remain future work. New functionality has compilation/build and startup evidence; live microphone, incoming Telegram, confirmation and sleep/reboot acceptance remain pending. Check [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) for dated evidence.

## Assistant architecture

The next build is described in [DEREK_ALWAYS_ON_PLAN.md](DEREK_ALWAYS_ON_PLAN.md). The shared foundation now includes a Features page, per-conversation model profiles, persistent Telegram/desktop voice context, durable commands and exact reminder/Calendar confirmation cards. New conversations default to Gemini; the Features page can select the current installation model instead. Existing conversations keep their selected profile and background research retains `MODEL_PROVIDER`. No provider is silently substituted.

Chat uses the asynchronous command API and retains its request ID while retrieving a result. Text, voice and Telegram mutations prepare a two-minute confirmation; confirm the exact action or cancel it. Workflow activation still requires Automations review. Command/action/delivery records are separate so a lost reply does not automatically execute an action again. Command event history uses JSON polling. Desktop speech audio now streams from Cartesia; model token streaming and a server audio socket remain planned.

`./scripts/start-services.ps1` now launches the managed local app by default. Use its explicit `-Celery` mode only for the separate legacy development stack. Local logs and database snapshots are in the ignored `.companion` folder. Keep the services and laptop running until cloud cutover.

For the spare Galaxy A32/Airtel number, see [PHONE_SETUP.md](PHONE_SETUP.md). Phone forwarding and a voice gateway are not configured yet.

## Fresh Windows installation

For the complete managed local setup, follow [LOCAL_APP.md](LOCAL_APP.md). Existing users should keep their ignored `.env`, database and paired browser profile. The commands below describe the optional development stack; stop the managed local runtime before using that stack.

### Legacy development stack

Python 3.11+ and Node 22+ are required. Docker Desktop provides PostgreSQL and Redis; SQLite is available for development without Docker.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit the ignored `.env` file. Generate a random Django secret and, for Calendar, a Fernet key. Select `MODEL_PROVIDER=gemini` with an accessible Gemini key/model, or `MODEL_PROVIDER=ollama` with a downloaded local tool-capable model. See [LOCAL_MODELS.md](LOCAL_MODELS.md) for Windows setup, RAM requirements and search differences. Missing integrations return a setup error; the app does not simulate provider success.

```powershell
.\.venv\Scripts\python backend/manage.py migrate
.\.venv\Scripts\python backend/manage.py create_owner YOUR_USERNAME
.\.venv\Scripts\python backend/manage.py runserver 127.0.0.1:8000
```

In another terminal:

```powershell
Set-Location web_dashboard
npm ci
npm run dev
```

Open `http://127.0.0.1:5173` and sign in with the owner account. The Vite proxy forwards `/v1` requests to Django. The service has one active owner and no public registration.

For reminders/background research, start Redis (`docker compose up -d redis`) and run these commands in separate terminals from `backend`, using the project virtual environment:

```powershell
..\.venv\Scripts\celery -A config worker --pool=solo --loglevel=INFO
..\.venv\Scripts\celery -A config worker --pool=solo --loglevel=INFO --queues=interactive --hostname=interactive@%h
..\.venv\Scripts\celery -A config worker --pool=solo --loglevel=INFO --queues=delivery --hostname=delivery@%h
..\.venv\Scripts\celery -A config beat --loglevel=INFO --schedule=../.companion/celerybeat-schedule
```

Create `.companion` first with `New-Item -ItemType Directory -Force .companion` from the root. Run each command in its own terminal. The first worker consumes the default research queue; the next two handle chat and delivery. Windows Celery runs with the solo pool for development; production workers run in Linux containers. Run only one Beat process. Without the corresponding workers and Beat, saved commands/jobs remain queued.

Alternatively, run the complete local PostgreSQL/Redis/app/worker/Beat stack with `docker compose up --build -d`; create the owner with `docker compose exec web python backend/manage.py create_owner YOUR_USERNAME`, then open `http://127.0.0.1:8000`. Local Compose is bound to loopback and uses development settings. Use the separate production configuration for hosting.

## Connect services

- **Gemini:** configure `GEMINI_API_KEY` and `GEMINI_MODEL`. Function calling and Google Search grounding are separate calls. Model IDs are configurable because availability changes. Every model request reserves daily usage before execution. The call/input limits are application guards; set provider-side billing alerts separately.
- **Calendar:** enable Calendar API in a Google Cloud project, create a web OAuth client, and register exactly the `GOOGLE_REDIRECT_URI` from `.env`. Set the client ID/secret and persistent `CREDENTIAL_ENCRYPTION_KEY`, then click Connect Google Calendar in Settings. Request scope is `calendar.events.owned`; the application exposes read/create/update, with no calendar deletion tool. Reconnect if Google revokes or expires the refresh token. Keep the encryption key stable to retain access to stored credentials.
- **Telegram:** configure the bot token and your numeric private chat ID. The managed local app starts one long-polling receiver without public HTTPS, validates the approved private sender/chat, and preserves durable offsets. For cloud deployment, use an HTTPS webhook instead: set a random webhook secret and run `python backend/manage.py configure_telegram https://YOUR_DOMAIN/v1/telegram/webhook/`. Do not run both receivers. Voice notes need the optional transcription dependencies.
- **Speech:** configure your Cartesia API key and licensed voice ID. Install `backend/requirements-voice.txt` to transcribe web/Telegram audio outside Docker. Docker includes the transcription package by default; the Whisper model downloads on first use. Desktop voice transcribes on the PC and sends the transcript to the API. Response text is sent to Cartesia for speech.

Provider credentials are configured on your machine or in AWS Secrets Manager, never in the dashboard or repository. Google refresh credentials are encrypted in the database. The browser profile is local and is never sent to the backend.

## Pair the Windows companion

Existing installations use the `LILYLEO_*` configuration keys and `LilyLeo` profile folder for compatibility. These identifiers are supported by Derek and retain access to saved browser sessions and execution checkpoints.

In dashboard Settings, pair a device and copy its one-time credential to `LILYLEO_DEVICE_TOKEN` in `.env`. Set `LILYLEO_API_URL` to your HTTPS deployment, or enable `LILYLEO_ALLOW_LOCAL_HTTP=true` for loopback development only.

```powershell
.\.venv\Scripts\python -m pip install -r companion/requirements.txt
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python -m companion login https://YOUR_APPROVED_SITE
.\.venv\Scripts\python -m companion run
```

Manual login uses a dedicated browser profile under `%LOCALAPPDATA%/LilyLeo`; bundled Chromium is the default. Stop the companion worker before signing in because only one process can use that profile. Sign-ins, passwords, MFA and CAPTCHAs are completed manually. Run the companion as your ordinary Windows user. Keep its state folder private.

For Google sign-in, set `LILYLEO_BROWSER_CHANNEL=chrome` (installed Google Chrome) or `msedge` (installed Microsoft Edge) in `.env`, then run the same `companion login` command. These channels open a normal, human-controlled vendor browser for login. Finish sign-in, close all windows for that Derek profile, then press Enter in the terminal. The worker later uses Playwright with the same browser channel and dedicated profile. Chrome and Edge each get a separate profile folder, leaving existing Chromium and personal browser profiles intact. Google can still require reauthentication or restrict automated access; use the Calendar OAuth connector for Calendar API tasks. See [Google's supported-browser guidance](https://support.google.com/accounts/answer/7675428?hl=en) and [Playwright browser channels](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge).

Closing the browser during manual login ends that session; it does not confirm a successful sign-in. Closed-browser cleanup is handled without a second `TargetClosedError` traceback. A sign-in session is ready only after you confirm success on the target website.

For voice in the local app, sign in once and use Ctrl+Alt+Space or Settings → Open voice. Local sign-in refreshes online voice access in Windows Credential Manager; sign-out revokes it. The separate command-line client `python -m companion voice` remains available, with `LILYLEO_USER_TOKEN` as an advanced legacy fallback. Device credentials cannot call chat APIs. Capture requires explicit arming; follow-ups retain context, sessions are bounded and unresolved requests can be retrieved without resending. See [VOICE_SETUP.md](VOICE_SETUP.md) for controls, confirmations and live acceptance still required.

## Workflow review and recovery

Describe a routine in chat or use the workflow definition editor. A saved workflow is a draft. Review tools, folders, sites, individual steps and trigger, then enable it. Editing a workflow disables it, advances its version, and cancels pending runs so it must be reviewed again. The default trigger is manual; once/daily/weekly triggers are supported.

Registered workflow tools:

| Tool | Arguments |
|---|---|
| `notify` | `message` |
| `research.run` | `topic`, optional `include_academic`, `report_kind` (`standard` or `project_ideas`) |
| `calendar.create` | `summary`, `start`, `end`, optional `description`, `location` |
| `calendar.update` | Same event fields plus `event_id` |
| `file.list`, `file.read`, `file.delete` | Absolute `path` |
| `file.write` | `path`, `content`, optional `overwrite` (default false) |
| `file.move` | `source`, `destination` on the same volume |
| `browser.run` | Ordered `actions`: navigate/read/fill/click/select |

File operations are limited to existing approved Windows subfolders. Reads/writes are UTF-8 and limited to 1 MB; moves never overwrite. Recursive deletion, scripts, shell commands and executable-code tools are unavailable. The companion's state and browser profile cannot be accessed through file tools.

For browser actions, approve exact HTTPS hostnames including any required asset hosts. A DOM mutation requires a unique visible `selector`, exact `expected_url`, and expected page text. Fill/select also require `value`. Sensitive actions declare `risk` as purchase/payment/account_security/permanent_delete; local target inspection can additionally request approval. Page wording detection is a conservative heuristic, so configure and inspect each website workflow before relying on it. Unexpected pages, authentication challenges, popups, dialogs and downloads stop execution. The browser uses pinned public addresses for reviewed domains and blocks other requests/WebSockets.

Example file workflow (replace the path with your actual approved folder):

```json
{
  "name": "Create a daily note",
  "description": "Write a note inside my approved folder",
  "steps": [{"tool":"file.write","args":{"path":"C:\\Users\\YOUR_USER\\Documents\\Assistant\\note.txt","content":"Today's priorities"}}],
  "allowed_tools": ["file.write"],
  "allowed_domains": [],
  "allowed_paths": ["C:\\Users\\YOUR_USER\\Documents\\Assistant"],
  "trigger": {"kind":"manual"}
}
```

Purchases, payments, account security changes and permanent file deletion require approval bound to the exact run, action and checkpoint. Website code and model responses cannot grant permission. Global/workflow pause prevents new actions; a request already sent can still finish. Offline desktop jobs wait in the database.

The local journal checkpoints mutations before and after execution. A crash, expired lease, or uncertain external response is marked `needs_attention` and is never blindly replayed. Inspect the website/file and Activity first. Cancel an uncertain server run before creating a new reviewed run. `python -m companion resolve JOB_ID NEXT_ACTION` only records a local checkpoint; it does not authorize or restart a server job. This design prevents automatic duplicate side effects; it does not promise exactly-once delivery through third-party services. Following a long outage, recurring schedules dispatch one catch-up occurrence and advance to the next future time instead of flooding missed daily/weekly actions.

Research findings require supporting source text from two independent registrable domains to be marked corroborated. Inaccessible/unsupported findings remain unverified. Automated evidence checking can be wrong; inspect citations for important decisions. Source fetches block private addresses and revalidate redirects. Academic search uses Semantic Scholar; optional API access improves availability under its rate limits.

## Verify and deploy

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python backend/manage.py check
.\.venv\Scripts\python backend/manage.py makemigrations --check --dry-run
Set-Location web_dashboard
npm test
npm run build
```

Tests use mocked providers and temporary files. GitHub Actions also runs against PostgreSQL, builds the dashboard, and validates Terraform. CI execution requires pushing this project to your repository; local checks do not imply CI has run.

See [infra/aws/README.md](infra/aws/README.md) for EC2/RDS/ElastiCache/S3 deployment. Live checks need your credentials, account authorizations, HTTPS/DNS and an online desktop. The health endpoint checks the database; inspect Settings/Activity and container logs for background worker and provider readiness. Histories remain until deleted. S3 prior versions and RDS backups expire separately according to their configured retention.
# Roadmap access

Open **Roadmap** in the local dashboard for the saved owner board. Read [the full product roadmap](PRODUCT_ROADMAP.md) and [mobile access notes](ROADMAP_MOBILE.md). The [portable mobile board](https://nagaram-kridey.github.io/Derek-AI/) contains a public snapshot with browser-local drafts; it does not control the laptop.

Desktop launcher sign-in and the opt-in local screen observation preview are documented in [DESKTOP_ACCESS_SETUP.md](DESKTOP_ACCESS_SETUP.md). The preview does not enable mouse input or send window content to a model.
