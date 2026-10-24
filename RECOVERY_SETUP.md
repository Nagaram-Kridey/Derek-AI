# Local runtime and recovery

Updated: 2026-10-24, Asia/Kolkata. See WORK_SESSION_2026-10-24.md for this session's evidence.

## What the backup contains

New `.derekbackup` archives contain a consistent SQLite snapshot and every local DOCX/PDF file referenced by that snapshot. The snapshot is taken with SQLite's online backup API, including committed WAL data. Database integrity and foreign keys are checked. A missing/out-of-scope report prevents publication; a report changing during capture requires a retry.

The manifest and file chunks are authenticated/encrypted with the configured credential encryption key. Files are hashed, lengths checked and paths validated. Archives are atomically published and verified by restoring to a new temporary directory. Memory usage is bounded by chunks rather than loading complete report files at once. The current archive limit is 2 GiB of plaintext and 10,000 files; larger installations require a different backup strategy.

Private companion chat, browser sessions, `.env`, Windows Credential Manager entries and model weights are excluded. The normal database does contain normal chat/task/account records and must be treated as sensitive. Preserve the encryption key separately; losing it prevents recovery. This is a local backup, not off-device disaster recovery.

Existing older plaintext and `.sqlite3.fernet` backups are preserved. The new verifier accepts only the new archive format. No retention cleanup or deletion of older backups has been performed.

Snapshot capture and verification use temporary **plaintext** staging files. Normal completion and handled errors remove them, but a process crash or forced shutdown can leave staging directories behind. Published archives are encrypted; this does not mean every temporary file is encrypted at rest. Use Windows disk encryption for laptop-at-rest protection. Abandoned staging cleanup needs a separate careful review so active captures are never deleted.

## Commands

Run from the project root with the configured virtual environment:

```powershell
.\.venv\Scripts\python.exe -m desktop.backup create
.\.venv\Scripts\python.exe -m desktop.backup verify "C:\path\to\archive.derekbackup"
.\.venv\Scripts\python.exe -m desktop.backup restore-to "C:\path\to\archive.derekbackup" --destination "C:\path\to\new-recovery-folder"
```

`verify` creates and removes an isolated temporary restore. `restore-to` requires a destination that does not already exist. It writes an **offline export**; it never overwrites the active database, changes credentials or starts workers. Do not manually point Derek at a restored database until pending reminders, deliveries, workflows and credentials have been reviewed; blindly starting old queued work can resend actions.

For an actual disaster recovery, preserve the damaged installation, stop the runtime, validate an archive, and review a migration/cutover plan before replacing any working data. Automated live cutover is deliberately not provided in this increment.

## Runtime behavior

- Status-file replacement retries brief Windows sharing violations; persistent status write failure is logged without stopping the service monitor.
- Optional tray, workspace, hotkey and backup faults report a category without raw exception messages. Other services continue to be monitored.
- Crashed owned services restart with bounded backoff. Failed containment rolls back the new process; independent model processes are not adopted or killed.
- Successful backups repeat daily. Failed backup work retries after fifteen minutes. Backup status uses a 26-hour freshness window instead of a process heartbeat timeout.
- Shutdown first drains work. After three minutes, remaining owned processes are stopped. Existing command recovery may take up to 25 minutes to classify interrupted running records; uncertain external effects must not be blindly replayed.
- Startup schema changes require a verified encrypted archive on an existing installation; daily startup plaintext snapshots are no longer created. Missing encryption configuration or missing reports can therefore block migration with a preparation failure.

## Acceptance still required

- [ ] Longer monitored runtime after reload and optional-component failure coverage review.
- [ ] Real Windows sign-out/sign-in, sleep/resume and forced launcher crash checks.
- [ ] Off-device backup destination and encryption-key recovery arrangement.
- [ ] Full disaster-recovery cutover with reconciliation of pending external work.

Passing a restore drill proves the captured files can be recovered, not that arbitrary restored jobs are safe to resume automatically.
