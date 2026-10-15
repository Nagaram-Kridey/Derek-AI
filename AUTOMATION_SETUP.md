# Setting up Derek automations

## 1. Start the background services

The dashboard/backend must be running. Start Docker Desktop and wait until its engine is ready, then run from the project root:

```powershell
docker compose up -d redis
New-Item -ItemType Directory -Force .companion
```

Open a separate terminal for each long-running command below. Run the worker and scheduler from `backend`:

```powershell
Set-Location backend
..\.venv\Scripts\celery -A config worker --pool=solo --loglevel=INFO
```

```powershell
Set-Location backend
..\.venv\Scripts\celery -A config beat --loglevel=INFO --schedule=../.companion/celerybeat-schedule
```

Run only one scheduler. Settings → Automation controls should report the scheduler as online after its first tick.

## 2. Start the desktop companion for browser/file workflows

Save the paired device credential in `.env` as `LILYLEO_DEVICE_TOKEN`. This setting is separate from the voice session token. The local installation currently selects installed Chrome with `LILYLEO_BROWSER_CHANNEL=chrome`.

Finish manual browser sign-in and close all Derek login/demo browser windows before starting the companion. From the project root:

```powershell
.\.venv\Scripts\python -m companion run
```

Keep the PC awake for browser/file work. Reminders and research run on the service host; desktop jobs wait if the companion is offline.

## 3. Describe and review the automation

Tell Derek the task, exact website or folder, and when it should run. For example:

> Draft a workflow that sends me a daily check-in notification at 09:00 Asia/Kolkata. No browser or file permissions are needed.

For browser work, name the website and the specific action or information to collect. Complex sites may require separately reviewed asset domains and page selectors.

In the dashboard:

1. Open **Automations**.
2. Inspect the draft's trigger, steps, tools, domains and folders.
3. Select **Review & enable** after reviewing them.
4. Select **Run now** for an initial run; inspect **Recent runs** and **Activity**.
5. Keep the recurring trigger enabled for scheduled runs, or use **Pause** to stop future runs.

For a simple reminder, **Automations → New reminder** provides a form for the message, once/daily/weekly recurrence and time. Times default to Asia/Kolkata.

## Delivery and permissions

- A configured Telegram token and chat ID allow outbound reminder delivery. Incoming Telegram commands separately need the public HTTPS webhook.
- Browser actions are limited to approved domains and reviewed page targets. Sign-ins, MFA and CAPTCHAs require manual handling.
- Sensitive purchases, payments, account-security changes and permanent deletions require an exact-action approval.
- Enabling a workflow is a separate user review step; a draft alone does not activate it.

## Your daily enterprise software and AI research draft

**Local-model option:** The current installation selects Ollama with downloaded `qwen3:4b`, avoiding the earlier Gemini quota requirement. A local greeting, public web search, five-project report generation and Telegram PDF delivery succeeded. The reviewed PDF has four pages and explicitly unverified evidence; the two MVPs were narrowed during setup review. DOCX was generated but its visual renderer requires missing LibreOffice. Search uses DDGS public results. See [LOCAL_MODELS.md](LOCAL_MODELS.md). The 11 AM draft still requires review before activation; CPU reports can take several minutes.

**Recovery update, 2026-10-15:** Docker is running again. Redis returned PONG; one Celery worker and one Beat scheduler are processing ticks and refreshing the scheduler heartbeat. The backend and dashboard have been restarted. The research draft remains disabled awaiting review; the earlier Gemini quota error has not been retried. The startup failure and offline status recorded below describe the initial attempt.

Docker recovered before settings or socket-folder changes were applied. No factory reset was performed. The error matches [Docker desktop-feedback issue 531](https://github.com/docker/desktop-feedback/issues/531); a successful restart does not establish a permanent fix for that reported bug. Avoid starting duplicate worker/Beat processes while the current ones are active.

- **Name:** Daily enterprise software and AI project ideas.
- **Time:** Every day at **11:00 AM Asia/Kolkata** (research starts then; report delivery follows completion).
- **Output:** Five distinct proposals, each with target users, problem, MVP, evidence and a heuristic score. The two highest scores receive suggested architecture, production features, implementation stages and validation risks.
- **Ranking:** Business value ×3 + feasibility ×3 + engineering depth ×2 + novelty ×2, for a maximum of 50. Each component is a model estimate from 1–5.
- **Evidence:** Research citations are retained. Facts without two supporting independent domains remain unverified. Project designs and scores are proposals, not validated market demand.
- **Freshness:** Include the execution date in the research request and check titles from up to 14 completed reports in the previous seven days. Exact repeated titles are rejected; semantic repetition cannot be ruled out.
- **Files:** Authenticated PDF and DOCX downloads in **Reports**; a PDF is also sent to the configured approved Telegram chat after a successful workflow run. Delivery failures are logged without automatic resending.
- **Permissions:** Only `research.run`; no browser account access or local folders are required. Public research uses the backend's protected network fetcher.
- **Review:** Open **Automations → Workflows → Daily enterprise software and AI project ideas → Review steps and trigger**. Use **Review & enable** after reviewing the displayed draft.

### Setup status recorded 2026-10-15

The draft is saved with ID `a7401ae6-1640-4864-a8fc-bc9e38c42dd4` and is **disabled**. No recurring task has been activated.

The first requested preview stopped on Gemini HTTP 429 (quota/rate limit); no preview file was generated. The failed entry is visible in Reports. Check the configured Google AI account's model quota/rate limits before another run. No provider key needs to be pasted into chat.

Docker Desktop failed during inference-socket initialization, so Redis and Celery scheduling have not come online. The local backend/dashboard can still show the draft. Keep the backend, Redis, worker and one Beat scheduler running on an awake PC, or deploy them to the planned always-on host, for daily operation. Incoming Telegram webhooks are not required for outbound PDF delivery.

The report-planning/provider changes were published in implementation commit b52f099. No new local automated test suite was run for this publication; its CI results have not been inspected.
