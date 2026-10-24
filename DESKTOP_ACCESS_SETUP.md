# Desktop sign-in and screen preview

Updated: 2026-10-24.

## Open Derek without repeated local login

Use **Derek.lnk** or **Open Derek** in the Windows tray. After an initial owner sign-in has saved its credential in Windows Credential Manager, the launcher can connect the local desktop page automatically. Opening the ordinary site URL in another browser still uses the normal login flow.

The launcher requests a one-use, 45-second handoff from the loopback API with its existing owner token. The page removes the handoff from its fragment and exchanges it once. The full owner token is never placed in a URL. The desktop page then uses the existing token/session mechanism. Logout revokes the owner token and forgets the Windows credential, so the next launch requires sign-in again.

If the handoff expires, close the Derek app window and reopen it from the tray, or sign in normally. The tray focuses an already-open window rather than opening repeated instances. Initial account setup and credential recovery still require the owner.

The exchange requires the exact loopback host/origin and an unexpired, unconsumed code bound to the current owner token. The launcher disables proxies/redirects for this credential-bearing request. A code for a previous token cannot restore a revoked session.

## Local screen observation preview

1. Open **Settings → Screen observation → Open local preview**, or choose **Screen observation · local preview** in the tray.
2. Select **Enable read-only observation for this local session**.
3. Choose a supported app and press **Approve selected app**.
4. Press **Read selected app** to preview accessible control names, roles, bounds and available patterns.
5. Use **STOP / revoke**, Escape or close the preview to withdraw consent. Consent expires after two minutes and the displayed preview is cleared.

The observation is bound to the selected window handle, executable, process ID and process creation time. A replaced/unavailable window, locked desktop or expired consent requires fresh approval. Known browser and terminal executables, common password managers, authentication-related windows and elevated apps are excluded. Password-marked controls are omitted before their names are read. This is not a guarantee that ordinary document text contains no secrets; choose the app deliberately.

Previews remain in this native window's memory. No screenshots are taken, no values/text patterns are read, and no screen data is sent to models, Telegram, the web API or logs. The screen reader process receives a reduced environment without Derek model/account credentials. A five-second watchdog cancels an unresponsive observation.

Available UIA patterns are descriptive metadata; their presence does not enable input. Mouse movement/clicks, typing, screenshots, cloud screen analysis and autonomous desktop tasks remain planned. Browser workflows continue to use their separate domain permissions and profile.

## Evidence and remaining acceptance

- UI Automation COM client initialized successfully on this Windows installation; required comtypes dependency installed.
- Isolated regressions cover permission default/expiry, stale instance rejection, reader cancellation, duplicate readers, password-control omission and bounded metadata.
- Live automatic sign-in API exchange is checked after rollout; full native browser/window interaction acceptance remains separate.
- Per-app native screen observation acceptance remains pending. Some apps provide incomplete accessibility information; errors/timeouts revoke the session rather than claiming a successful read.
- A later batch must implement reviewed actions with fresh observation IDs, exact target checks, risk approvals, a shared interaction lock and an emergency stop before mouse access is enabled.
