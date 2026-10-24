# Desktop access batch — 2026-10-24

Scope: automatic local launcher sign-in and Stage 1 local screen observation. Reviewed input, mouse, screenshot/model transport and general desktop task execution remain later milestones.

## Implementation evidence

- Added expiring one-use desktop launch grants, token-revocation binding, strict local request checks and redirect-free credential handoff.
- Added fragment consumption and a shared exchange for duplicate React effects. Normal website access retains login; saved Windows credentials support the desktop launch.
- Added a native, off-by-default, two-minute per-window UI Automation preview, selected instance checks, elevation/known-sensitive-app restrictions, password-marked control omission and an immediate stop/revoke control.
- Preview data stays local. The reader runs with a reduced environment, bounded response bytes and an independent timeout; no model tools, screenshots or input API are exposed.

## Review checkpoints

- **Authentication review:** fixed redirect handling, invalid JSON handling, concurrent issuance serialization and expired-window instructions. Tests cover origin denial, actual logout, replaced grants and inactive users.
- **Observation review:** fixed stale callbacks after reapproval, duplicate reads with pending results, spawn-failure cleanup and a potentially blocking IPC receive. Receiver work now runs off Tk; the UI checks an in-memory bounded queue and revalidates scope before display.
- **13:18 IST:** stayed within this desktop-access batch. Live handoff launch/exchange returned HTTP 200, returned the existing owner session without displaying it, replay returned 401, and unauthenticated ordinary API access returned 401. Screen data was not inspected or uploaded.

## Acceptance boundary

- UI Automation COM client initialized successfully on Windows.
- Isolated observation regressions passed for consent expiry, stale instances, revoke, duplicate reads, protected control names, failed start and result handling.
- Native per-app observation and interactive desktop browser handoff acceptance remain pending; do not infer these from API/unit checks.
- Both `autologin` and `observe` roadmap blocks stay in progress until user-facing acceptance. General mouse control remains planned.

Instructions: [DESKTOP_ACCESS_SETUP.md](DESKTOP_ACCESS_SETUP.md).

Final automated verification: **214 Python tests passed, 1 opt-in browser test skipped**; nine dashboard tests and Settings rendering regression passed. Production build, migration consistency and selected Ruff checks passed. Both roadmap blocks saved with HTTP 200. A final managed reload was requested after the review fixes; native browser/per-app observation acceptance remains pending.

Managed reload completed: all configured services returned fresh ready status; supervisor running and local health HTTP 200. No active screen consent was granted during rollout.
