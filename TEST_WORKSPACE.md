# Isolated tester workspace

This is a manual laptop-hosted trial for the first ten Google accounts. Personal Derek remains on port8000; the trial uses loopback port8010 and `.trial-workspace/` for its own database, credentials, media, dashboard snapshot, runtime records and logs. Nothing under that directory belongs in Git or a public attachment.

## Setup

Run from the repository root using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m testing_workspace init
.\.venv\Scripts\python.exe -m testing_workspace configure
.\.venv\Scripts\python.exe -m testing_workspace admin YOUR_TEST_ADMIN
npm --prefix web_dashboard run build
.\scripts\start-test-workspace.ps1
```

`configure` prompts locally for up to ten invited Google email addresses, a **separate** Google Web client ID, a separately provisioned model-router credential, the assigned ngrok hostname, and the ngrok authtoken (hidden). Open signup is enabled for this trial: no invitation list is required, and registration closes after ten Google accounts (returning accounts can still sign in). Invitation-only mode remains available by selecting No at the open-signup prompt; in that mode blank invitations deny all Google testers. New admin credentials are entered through Django's interactive password validation; personal owner credentials/tokens are never imported. The default assigned hostname is `peddling-stardust-untapped.ngrok-free.dev`; confirm it is still your account's assigned domain.

Install the official ngrok agent separately and put it on PATH. Configure the exact HTTPS assigned-domain origin in the separate Google OAuth client. No redirect URI is needed for this GIS credential callback flow. Leave the current personal Google client unchanged. The trial Google challenge cookie is Secure: complete Google sign-in through the HTTPS tunnel, not the local HTTP preview.

## Publish and stop

```powershell
.\scripts\start-test-workspace.ps1 -Publish
.\.venv\Scripts\python.exe -m testing_workspace status
.\scripts\stop-test-workspace.ps1
```

Starting with Publish requires client ID, router credential, domain, ngrok config and an existing trial admin. Only `http://127.0.0.1:8010` is tunneled; the router3001 and personal8000 are not. Start merely requests a tunnel; verify the public HTTPS login and ngrok free visitor notice before sharing. Inspector body capture is disabled. The workspace stops if its ngrok process exits; review `.trial-workspace/logs/runtime.log` and account quotas before restarting. It never purchases an upgrade.

Stop is graceful: it waits for any current request to finish, then ends only this workspace and its own tunnel. `status` must show running:false before restore/configuration. Personal processes are never killed. Keep the laptop awake and connected for tester access. There is no Windows autostart or service installed.

The trial supports text chat, history and admin analytics. Host tools, scheduling, Calendar, Telegram, audio and research are disabled even for trial admin. Usage defaults are20 actual model calls per tester/day,200 shared/day and one unfinished request per tester, resetting midnight Asia/Kolkata.

## Backup and restore

```powershell
.\.venv\Scripts\python.exe -m testing_workspace backup
.\scripts\stop-test-workspace.ps1
.\.venv\Scripts\python.exe -m testing_workspace status
.\.venv\Scripts\python.exe -m testing_workspace restore ".trial-workspace\backups\SNAPSHOT_DIRECTORY"
```

Snapshots contain a SQLite online backup plus trial media, with integrity checking. Startup backs up before migrations; the worker also backs up after24 hours of operation (after an active request finishes). Restore accepts only snapshots in this workspace's backup directory, requires it stopped, and first preserves the current data. Snapshots are local sensitive plaintext; keep `.trial-workspace` private. They do not contain encryption keys or configuration, and are intended for restoring into this same workspace. To recover the whole trial on another machine, securely preserve config.json as well; never share it in chat. No automatic off-device backup is configured.

## Future domain

When you obtain `derek.co.in`, use `test.derek.co.in` with a named Cloudflare Tunnel. Register that HTTPS origin with the trial Google client and adjust the exact allowed-host configuration; the test database stays in place. The current configure prompt intentionally accepts only ngrok-assigned domains, so the custom-domain cutover is a later explicit change. No GoDaddy purchase or DNS change is performed by these tools.

## Current acceptance

The isolated database and fresh keys are initialized; no admin or fake tester was created. Local start/health200/backup/stop were verified. Public tunnel and real two-account Google acceptance await your local configuration. Run `python -m testing_workspace --help` for commands; no arguments display help.

## Open signup update

Open signup is enabled in the local trial config. Only verified Google accounts can register; the first ten subjects consume the ten-account limit, including inactive accounts. Existing testers can return after registration closes. Usage limits and admin isolation remain unchanged. Eleven focused policy/runtime tests passed, including account11 denial and returning-login acceptance. Public publication still awaits private router/ngrok credentials and test-admin creation. Google may independently restrict access through its app audience settings.

## Individual Telegram connections

Each tester links their own private Telegram chat. Create a new dedicated test bot in BotFather, never the personal Derek bot. With trial stopped, run `.\.venv\Scripts\python.exe -m testing_workspace telegram-configure`, enter its token in the hidden prompt and username without @, then restart. Settings Telegram generates a five-minute single-use private-chat deep link. Press Start in the bot, then refresh connection status. Group chats cannot link. Chats already linked to another account cannot be reassigned without disconnecting. Disconnect invalidates outstanding grants. Inbound text uses only its bound user's configured-model conversation and usage limits. Explicit send accepts only that user's completed answer; no personal-owner fallback exists. Unknown send outcomes are not automatically retried.

Treat linking URLs as short-lived secrets; only their digest is stored. Bot polling never removes an existing webhook. Logs omit tokens, messages and exception details. Real Google/Telegram two-account acceptance requires the dedicated bot and user-completed links; mocked transport tests send no external messages.
