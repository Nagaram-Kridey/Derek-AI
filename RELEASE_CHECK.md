# Derek — pre-publication review and tests

Date: **2026-10-19 · Asia/Kolkata**. Requested scope: review the local assistant expansion, test it, fix failures and push to `Nagaram-Kridey/Derek-AI`.

## Results

| Check | Result |
|---|---|
| Python regression suite | **116 passed**, no warnings in the final run |
| Dashboard tests | **8 passed** |
| TypeScript / Vite production build | Passed |
| Python compilation / selected Ruff error and undefined/unused-name rules | Passed |
| Django system check / migration consistency | Passed; no missing migrations |
| Python installed dependency consistency | `pip check`: no broken requirements |
| Dashboard dependency audit | `npm audit`: zero known vulnerabilities, including development dependencies |
| Terraform | `validate` passed using the installed provider cache; no deployment |
| Local / production Compose | Configuration validation passed; no containers started |
| Credential scan | Candidate tracked/unignored files checked against configured sensitive values and common private-key/API-token patterns; no matches. A staged scan is repeated before commit |
| Production-code line coverage | **49%** (3,094 / 6,301 lines). Tests are excluded from this percentage; coverage is not exhaustive |

The Docker engine is not running on this laptop, so PostgreSQL/container execution was not performed locally. GitHub CI is configured for Linux/PostgreSQL, Windows, dashboard tests/build and Terraform validation. Its remote result is recorded after publication.

## Added regression coverage

- Command request replay, changed-request rejection, cancellation tombstones, conversation reset/profile pinning and owner isolation.
- Exact two-minute confirmation binding, repeated confirmation, expiration/replacement/pause/cancel behavior, unbound voice/Telegram yes, and uncertain Calendar outcomes without replay.
- Create-form retry safety, stale schedule edits, notification read state, export exclusions and private-response headers.
- Local conversation/research/delivery/scheduler dispatch, command polling versus submission throttling and cancellation connection lifetime.
- Durable PDF delivery success, known retry delays, unknown outcomes, explicitly requested copies and ordered message delivery.
- Telegram sender/group checks, compact signed buttons and signature/revision/owner/channel tampering.
- Local-model origin/metadata restrictions, remote-delegation rejection, reasoning filtering, usage counts, invalid tool calls, transport cancellation and shortlist tie guards.
- Private local history/export/delete, interrupted replies, token-bound voice state, Windows credential encoding, process ownership, bounded log rotation and stale runtime records.
- Simulated voice/VAD: capture starts explicitly, a complete readback arms its exact proposal, interrupted/stale/expired readbacks do not authorize actions, and recording boundaries are bounded.
- Frontend API credential confinement, normalized path escape rejection, redirect refusal, abort/error handling and browser-storage recovery.

## Fixes made during review

1. Check research cancellation before creating a model provider.
2. Preserve the caller's database transaction when cancellation is probed; helper-thread connections still close outside transactions.
3. Reject normalized/encoded API paths that escape `/v1/` before attaching credentials.
4. Exclude SQLite WAL/shared-memory/journal files, local runtime state, logs and private-key/state files from Docker context.
5. Make tests use a disposable database/media directory, dummy integration configuration, no broker, blocked unmocked connections and mocked native credential access. Windows asyncio's internal socket-pair wakeup is allowed separately from application networking.
6. Correct historical tests that expected immediate reminder execution or Telegram messages lacking a verified private sender. Confirmation and identity requirements were retained.

## Boundaries

These are isolated automated checks and operational review, not a certification of production readiness. Live microphone/speakers, account-authorized Calendar changes, incoming Telegram conversation/voice, full signed-in browser workflows, Windows lock/sleep/reboot, crash injection and off-device restore remain acceptance work. No paid model probes, test Telegram messages, phone changes or cloud deployment were performed for this verification.

Publication status: local checks passed; implementation commit, remote SHA and GitHub CI outcome are recorded after pushing.
