# Derek — use it on this laptop

Updated: 2026-10-19 (Asia/Kolkata)

## Open Derek

Double-click the **Derek** desktop shortcut or `Derek.vbs` in this project. The workspace opens at **http://127.0.0.1:8000**, in its own Edge/Chrome app window when an installed browser is available. This dashboard profile is separate from your normal browser and the automation browser. Sign in with **Kridey** and your existing password. “Keep me signed in on this browser” is optional.

Closing the browser leaves the assistant running in the Windows tray. The tray menu opens the workspace, voice window, private voice/chat, logs, restart and quit. **Ctrl+Alt+Space** opens or focuses the current voice window; **Listen** explicitly arms capture. The shortcut does not silently start recording. Quit/restart lets current worker jobs finish and asks managed voice sessions to stop. Long research can therefore delay a requested exit; stop that report in Reports if you want it cancelled. Stop never silently undoes a saved account action.

Windows sign-in startup is enabled on this laptop and can be changed in Settings or the tray menu. It starts the assistant quietly, with no microphone recording. The source folder and `.venv` must stay in place; this is a local source installation, not a signed standalone installer.

## What works without Docker

The local launcher serves the **built dashboard and API on one address**, using Waitress. Separate database-backed workers handle conversations, research, reminders/delivery and scheduling. Local mode needs neither Redis nor Docker, nor a running Vite/Node development server. The existing cloud/Celery deployment remains a separate option.

- **Today:** upcoming routines, updates, and current service health.
- **Chat:** readable replies, sources, exact confirmation cards, conversation search and retained request IDs. A lost connection offers **Retrieve reply**, **Stop response**, and **Command history**; retrieval does not submit the command again.
- **Routines:** create/edit reminders and research schedules, choose multiple weekdays, inspect occurrence history, and pause/resume them. Dates default to Asia/Kolkata. The edit form shows the schedule before you save it.
- **Workflows:** start from a check-in, website, local-note or research template. Review exact permissions and trigger before enabling. Advanced definitions are still available. Editing disables a workflow and cancels pending runs until it is reviewed again.
- **Reports:** search, read in the app, download PDF/DOCX, follow evidence labels, see research stages and stop queued/running work. Scores and project suggestions are estimates; unverified evidence stays labeled.
- **Command history:** inspect saved replies, action outcomes, current proposals and the event timeline. An uncertain outcome requires inspection before another action is requested.
- **Updates:** reminders and report notices remain in the app even when Telegram delivery is unavailable. Marking read does not delete the audit trail.

The local supervisor restarts crashed processes with bounded backoff. Windows job ownership groups the managed service tree for cleanup, including existing Python venv children. Failed preparation keeps the narrow local stop/restart controls available. Crash and reboot behavior still needs live acceptance. It never replays a record already marked running or uncertain after a crash. Such records become needs-attention under the existing timeout rules. It refuses to overlap this runtime with the project's development/Celery services. SQLite uses WAL and short serialized write transactions. New create forms use request IDs retained during retries, with a 30-day replay window. Reusing an ID with different form values is rejected.

The launcher saves a plain local database snapshot before migration and a daily startup snapshot. A managed backup job additionally creates a daily SQLite snapshot while the app stays running, encrypted when the existing credential encryption key is configured. Settings shows the managed snapshot status. Preserve that key to read encrypted snapshots; private-chat history and separate report files are outside this snapshot’s scope. Backup files inherit this Windows folder's access permissions. A full off-device restore exercise remains pending.

## Telegram on an awake laptop

With the existing bot token, approved chat and approved sender configured, local mode can receive private text and voice notes through **long polling**. A public HTTPS webhook is not required for this local option. The receiver stores accepted updates and its offset before acknowledging later batches. Unknown senders/groups are ignored.

The poller never deletes or replaces a registered webhook. If another poller or a webhook is active, its status shows that conflict and it waits. It respects Telegram retry delays. Use one receiver per bot. Set `DEREK_TELEGRAM_POLLING=false` to disable local polling before a future cloud webhook cutover.

Reminder/Calendar readbacks include **Confirm change** and **Cancel** buttons signed for the exact proposal, owner and revision. A bare Telegram “yes” cannot approve an arbitrary pending action. Expired or replaced buttons cannot create a new action. Telegram outages do not re-execute saved actions; uncertain sends remain needs-attention rather than being blindly duplicated. New report PDFs have their own saved delivery status and queue, separate from research. Reports also offers an explicitly confirmed “Send PDF to Telegram” action when you want another copy.

This mode still depends on an awake laptop and internet. Telegram voice replies are not enabled yet; voice notes are transcribed and receive concise text replies. Google Calendar still requires your OAuth consent. Signing in to the managed local app refreshes its desktop session token in Windows Credential Manager. Signing out revokes online voice until you sign in again; private chat remains separate. Provider keys and the credential-encryption key still use the ignored environment configuration. See [VOICE_SETUP.md](VOICE_SETUP.md) for normal desktop voice and [PRIVATE_CHAT.md](PRIVATE_CHAT.md) for the separate local mode.

## Everyday controls

| Need | Where |
|---|---|
| Talk or type | Chat → Voice window, Ctrl+Alt+Space, or the tray |
| Read a report | Reports → Read report |
| Change the 11 AM routine | Automations → edit the workflow → review and enable it again |
| Stop research | Reports → Stop research |
| Stop an unfinished reply | Chat → Stop response, or Command history |
| Pause new automation work | Settings → Pause all |
| Mute the microphone | Native voice window → Mute / Esc, or voice console `/mute` |
| Start when signing in | Settings → Laptop app, or Windows tray → Start at Windows sign-in |
| Quit safely | Windows tray → Quit after current work |

Purchases, payments, account-security changes and permanent deletion retain their approval rules. Browser CAPTCHA/MFA and unexpected pages pause for manual attention. File and browser steps stay inside their reviewed scopes. Assistant code, state, credentials and its dashboard/automation profiles remain protected from file workflows. Phone forwarding has not been configured.

## Developer / recovery commands

```powershell
# Start the tray app (a second start opens the existing instance)
.\scripts\start-desktop.ps1

# Inspect local runtime records without exposing credentials
.\.venv\Scripts\python.exe -m desktop status

# Drain and stop, or drain and restart
.\.venv\Scripts\python.exe -m desktop stop
.\.venv\Scripts\python.exe -m desktop restart

# Rebuild the dashboard after source changes; then restart the tray app
.\scripts\build-local.ps1

# Install dependencies on another Windows source checkout
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r companion/requirements.txt -r desktop/requirements.txt

# Create a current-user desktop shortcut, optionally with sign-in startup
.\.venv\Scripts\python.exe -m desktop.install --autostart
```

The legacy Celery startup helper is now explicit: `scripts/start-services.ps1 -Celery`. Stop the local tray runtime before using it; never run both schedulers. The default helper starts the local tray app.

Runtime records and bounded service logs live under the ignored `.companion/runtime/` folder. Database backups live under `.companion/backups/`; these are local copies, not an off-device disaster-recovery system. Preserve the ignored `.env` encryption key separately before moving encrypted Calendar credentials. Do not send credential/config files into chat or commit them.

## What remains unverified

Static builds and startup inspection do not establish end-to-end correctness. Live microphone playback/interruptions, exact real reminder/Calendar confirmation, Telegram conversation delivery, Windows lock/sleep/reboot, and crash recovery still require acceptance. CPU-only local generation can be slow; no latency guarantee is made. Cloud hosting, a signed installer, wake word and the Airtel phone gateway remain later work. Ctrl+Alt+Space is implemented to open or focus the voice window.
