# Google tester accounts and model analytics

This setup supports a small testing group. Existing owner data stays under the existing admin account. New accounts use Google sign-in and have separate chat history. Testers cannot use the host's desktop controls, shared Telegram integration, workflows or owner settings.

## Enable Google sign-in

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project and configure Google Auth Platform branding and audience for Derek. If Google requires test-user registration for your selected configuration, add the intended testers.
2. Create an OAuth client of type **Web application**. Register the exact **Authorized JavaScript origins** you use: initially `http://127.0.0.1:8000`; add `http://localhost:8000` or `http://127.0.0.1:5173` only if actually used. A future shared HTTPS URL must also be registered.
3. Put the public client ID in the local `.env`:

   ```dotenv
   GOOGLE_SIGN_IN_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
   ```

4. Restart Derek through the managed desktop runtime. Open the login page in an ordinary supported browser if an embedded browser blocks Google's popup or federated sign-in.
5. Sign in with two distinct Google test accounts and verify their conversation lists remain separate. The existing admin still signs in through **Admin sign in** or the desktop handoff. Google email matching never automatically links or promotes an account.

No client secret is needed for this Google Identity Services ID-token flow. The existing `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` Calendar settings are separate. Never place a Calendar secret in the frontend.

Official setup and validation references: [Google GIS setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid), [server token validation](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

## Admin analytics

Open **Profile → Model analytics**. Choose the last24 hours,7 days or30 days. The dashboard shows call/failure/slow counts, median/p95 provider time, command queue/total time, account activity, requested model/route breakdown and recent sanitized issues. Model observations begin after this update; missing historical provider measurements are shown as no samples. Requested router profiles may use several underlying models. No prompt or response content is included in analytics.

## Account boundary

The server validates Google's signature, issuer, audience and expiry through google-auth, checks verified email, and identifies accounts by the immutable Google subject. Each login requires a short-lived, single-use nonce challenge bound to an HttpOnly browser cookie. Replayed credentials without that challenge are rejected. Existing admin accounts are never selected by email matching. Server permissions and tool/worker guards enforce tester isolation even when someone calls APIs directly.

The existing persistent DRF token/session architecture is retained for this testing scope. A public hosting link and production rollout are separate work. Creating a Google client ID alone does not expose your laptop to others.

## Client configuration check — 1 November 2026

Owner-supplied Web client ID is configured locally; live /v1/auth/config/ reports enabled and the GIS button renders. Google currently returns origin-not-allowed for http://127.0.0.1:8000. Confirm that exact Authorized JavaScript origin is saved on the same OAuth client, and allow Google configuration propagation before retrying. Real sign-in remains unverified.
