# Derek roadmap on mobile

Public site: https://nagaram-kridey.github.io/Derek-AI/

The portable board is a static snapshot dated October 23, 2026. Open it from a phone on any network, even while the laptop is off. Use the browser's Add to Home Screen option for a shortcut. Offline loading is not guaranteed; no service worker is installed.

## What works

- View/search/filter all 35 feature groups and their status, phase, priority and dependencies.
- Add or duplicate blocks, edit scopes, track test plans/results and add evidence.
- Save drafts in that browser's local storage. Private browsing, clearing site data or changing browsers can lose these drafts; use Export JSON regularly.
- Copy one feature prompt or the enabled “now” plan into Codex for implementation.
- Print or save the visual board as PDF; the overview is also available at `roadmap.svg`.

## Data and synchronization

This public site never accepts Derek tokens and never calls the laptop API. Its published catalog omits owner-specific descriptions, setup notes, test evidence and runtime state. Editing it does not change the public site for anyone else or update the laptop database. Transfer changes by JSON export or copyable prompts. Keep credentials out of notes.

The local dashboard at `http://127.0.0.1:8000/#roadmap` uses the authenticated database with owner isolation, dependency validation and optimistic concurrency. Its planning changes also do not start tasks or grant permissions. Test results are manual evidence records, not automatically certified executions.

## Publishing updates

The published branch is `roadmap-pages`, independent of main and uncommitted application code. GitHub Pages uses that branch's root. To update:

1. Review the starting catalog and rebuild it using `python scripts/build_roadmap_catalog.py` when appropriate. This never overwrites saved owner boards.
2. From `web_dashboard`, run `npm exec -- vite build --config vite.roadmap.config.ts`.
3. Run `python scripts/prepare_mobile_roadmap.py` from the project root. This reads only the checked-in catalog and visual, never `.env` or the database.
4. Review the generated `web_dashboard/dist-roadmap` assets, commit those files to the existing `roadmap-pages` branch and push. Do not force-push or publish the project root.

Existing phone drafts are intentionally not overwritten by a new published catalog. Export drafts before clearing site data to load a fresh catalog. Automatic merging/import is not implemented yet.

## Next: truly shared remote control

- [ ] Select a private authenticated remote path (VPN/private tunnel to laptop, or an authenticated hosted backend).
- [ ] Verify device access, TLS, allowed hosts/origins, revocation and audit trails before making live controls reachable.
- [ ] Keep laptop awake for a laptop-hosted backend; cloud hosting is required for controls while it is off.
- [ ] Add authenticated synchronization and conflict resolution; never embed backend tokens in public Pages assets.
- [ ] Build a registered isolated test runner and server-enforced feature switches independently of planning metadata.

GitHub Pages serves static files and does not execute the Django backend. Its site is public. See [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).
