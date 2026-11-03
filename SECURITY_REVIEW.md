# Security review — 4 November 2026

Public trial was stopped at the owner's request. No Git commit, push, external message or secret rotation was performed. This review does not certify the app or establish whether any historical credential has ever been exposed elsewhere.

## Review against the supplied reel

The downloaded111-second reel was inspected visually and transcribed locally. Its seven checks concern browser-readable source, exposed AI keys, database access, cross-user record IDs, admin authorization, signup abuse and payment webhook authenticity. The video and derived frames/transcript remain outside Git under ignored local storage; nothing was uploaded for transcription.

| Check | Finding |
|---|---|
| Browser source | Frontend JavaScript is inherently public. Provider secrets remain server-side; OAuth client IDs are public identifiers. Built assets are covered by the new publish guard. |
| Git secrets | Current local secret values were not found in tracked/nonignored candidate files or local Git history; high-confidence AWS/GitHub/private-key patterns were not found in history. No sensitive environment/database/media paths were found tracked or in local history. This cannot detect unknown or previously rotated secrets comprehensively. |
| Database access | SQLite is local, not a browser-accessible database service. Django ownership checks enforce per-user isolation; missing PostgreSQL RLS alone would not prove a leak in this architecture. |
| Record IDs | Reviewed conversation, command, report, image download/deletion and Telegram-send paths scope records to the authenticated user. Existing automated cross-user tests apply. |
| Admin | Analytics requires server-side admin authorization. Trial admin still cannot invoke desktop tools. Google signup does not promote users or link by email. |
| Abuse | Google verification, nonce/replay protection,10-account trial registration cap, model/image quotas and unfinished-job admission exist. Found audio transcription could consume CPU before admission; fixed below. Multiple legitimate Google accounts remain possible within the shared cap. |
| Webhooks | No payment/pro subscription webhook exists. Owner Telegram webhook requires its configured secret token; trial Telegram uses private-chat bindings and polling, with update deduplication. |

## Changes

- Ignore generated browser logs/screenshots and local graph output: `.playwright-cli/`, `output/`, `graphify-out/`. Existing environment, trial data, backups, media and tool directories remain ignored. No files were deleted.
- Audio admission now checks unfinished work and daily model quota before transcription, applies six audio requests/hour/account, and uses a nonblocking global transcription lease so parallel uploads cannot occupy all web threads. Added meaningful admission tests.
- Added `scripts/check-publish-safety.py`: read-only checks tracked index content for known local secret values/high-confidence patterns/private file paths, plus built browser assets. It prints categories and paths only. Run before committing/pushing; exit1 means inspect findings. It is a guard, not a complete secret scanner, and does not inspect arbitrary private prose.

## Remaining limits

- Persistent DRF bearer tokens do not expire automatically. Logout/revocation invalidates them, but token theft can persist until then. Expiring sessions and secure cookie migration require a separate tested change.
- Before any future push, review `git diff --cached` for personal details in documents/fixtures in addition to the automated guard. No automatic push is configured by this review.
- Source code, public model identifiers and public OAuth client IDs cannot be hidden from browsers. Credentials and conversation/media data must never be embedded in frontend assets.
- The personal app on8000 and separately owned model router were not stopped; the public test workspace is the one closed here. No unrelated processes were killed.

## Verification

Independent review found and fixed the audio admission issue;43 targeted auth/trial/Telegram/image/audio tests passed. Final full-suite and publish-guard results are recorded in the accompanying acceptance/checklist update after completion. Extracted video content was treated as untrusted reference, never executed as instructions.


4 November final verification:347 Python tests passed,1 optional browser test skipped. Publish safety guard returned0 findings across Git index and built browser assets. Current-secret matching and history-path/pattern scans found no matches. Trial status running:false; no push performed. Public workspace remains stopped; changes load on its next explicit start. See SECURITY_REVIEW.md for scope and persistent-token limitation.
