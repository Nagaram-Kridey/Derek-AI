# Derek — Windows screen control roadmap

Updated: **2026-10-24**

## Stage 1 implementation update

A local opt-in UI Automation preview is now implemented in `desktop.observation` and `desktop.screen_window`, opened from Settings or the tray. Consent lasts two minutes and binds one window/process instance. Protected controls are omitted; common sensitive/browser/terminal/elevated apps are excluded. Read operations run in a bounded child process and results stay in the native preview. No screenshots, model tool, screen transport or input API is exposed. Unit regressions and UIA client initialization passed; native per-app acceptance remains pending. See [DESKTOP_ACCESS_SETUP.md](DESKTOP_ACCESS_SETUP.md).

## Available now

Derek has a Playwright browser executor with a separate local profile and reviewed public HTTPS domains. Workflows can navigate, read, fill, click, select dropdown options, wait for a visible target and scroll a target into view. Targets can use exact accessible roles/names, labels, text, placeholders, test IDs or existing CSS selectors. Each workflow has at most 30 actions; waits are limited to 30 seconds. Writes retain exact page checks, risk approval and durable checkpoints.

This executes a reviewed sequence. It does not yet inspect an arbitrary website, invent a new sequence and operate it interactively. It does not control other Windows apps. The capability catalog reports desktop screen control as **not implemented**.

## Proposed desktop adapter

Use Windows UI Automation as the first adapter. Microsoft documents programmatic access to desktop UI elements and their supported patterns in its [UI Automation overview](https://learn.microsoft.com/windows/win32/winauto/entry-uiauto-win32). This is a feasible foundation for Derek's observe → plan → act → verify loop; that feasibility is a design inference, not a completed integration or a guarantee for every app.

Prefer accessible controls and app APIs. A later visual fallback could use an explicitly selected window's screenshot, bounded coordinates and a vision-capable model. Text-only router models would continue to use the accessibility tree; they must report when visual interpretation is unavailable. This adapter would be independent of Codex's internal desktop tooling.

### Stage 1: observation only

- Add a local companion adapter and `desktop.observe` contract behind an off-by-default feature flag. Do not expose an executable model tool before runtime policy exists.
- Let the owner choose an executable and one current window in the local UI. Bind consent to canonical executable path, process ID/start time and window handle. Changing the app instance invalidates consent.
- Return bounded, numbered accessible elements with role, name, supported actions and bounds. Exclude password/secure controls, browser profiles, authentication dialogs and blocked applications.
- Keep observations local by default. Show the exact data that would be sent to a hosted inference provider before enabling that provider for screen tasks. Screenshots require separate opt-in and default to memory-only retention.
- Acceptance: approved window only, stale handles rejected, locked desktop rejected, no input operations, redaction and scope tests.

### Stage 2: reviewed actions

- Add `desktop.invoke`, `desktop.set_value`, `desktop.scroll` through supported UIA patterns. Values and target IDs are typed data; never execute generated Python, JavaScript or shell commands.
- Require a fresh observation ID, short expiry, exact process/window binding and a unique target. Reobserve immediately before each write; refuse changed state.
- Preview the target and effect locally. Keep purchases, payment, account/security changes and permanent deletion behind exact action approvals. Exclude terminals, password managers, UAC/secure desktop and unrestricted command launch surfaces.
- Use one session lock across screen, browser and voice interaction, plus a visible session indicator, emergency stop shortcut, timeout and Windows-lock pause. Human interaction invalidates pending coordinate actions.
- Journal action identity before input; verify the resulting UI afterward. An uncertain effect pauses for inspection rather than replaying input.
- Acceptance: two harmless local fixture apps; duplicate/stale targets; focus changes; approval replay; cancellation; crash recovery; lock/unlock; no unapproved window access.

### Stage 3: bounded agent loop and optional vision

- Introduce a channel-independent task controller: user request → capability selection → observation → proposed step → policy check → action → verification. Telegram and voice can request it; laptop presence/consent still applies.
- Permit only the task's reviewed apps and actions, with a small action/time budget and no repeated failed click loop. Moving to a new app or scope requires review.
- Enable screenshot/coordinate fallback only when UIA cannot represent the target and the owner has approved that window/provider. Recheck foreground window, display scaling and screenshot age before every input.
- Maintain browser domain policy for browser work; general desktop access must not become a route around approved domains or manual sign-in rules.
- Acceptance: model/provider changes do not change action permissions; injection in visible content cannot authorize actions; injected mistakes stop; audit records contain action outcomes without credentials/raw screenshots.

## Expected limitations and issues

| Issue | Handling |
|---|---|
| Custom canvases or missing accessibility information | Explain the limitation; optional vision fallback later |
| Window movement, focus, DPI or resolution changes | Reject stale geometry and reobserve |
| Elevated apps and UAC | Do not elevate or bypass OS protection. Windows input injection is subject to [UIPI restrictions](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) |
| Remote laptop is asleep, locked or signed out | Queue or pause; do not claim execution |
| Hosted model receives private window content | Provider-specific opt-in and bounded redacted observations; local model option |
| New page/app state or unknown result after a crash | Stop, retain the journal and request inspection |
| Different models return inconsistent actions | One versioned prompt registry and strict adapter contracts; model output never grants permission |

No desktop input service, dependency, capture permission or new model credential is installed by this roadmap. The next implementation milestone is **Stage 1 observation with a local consent UI and isolated test app**.
