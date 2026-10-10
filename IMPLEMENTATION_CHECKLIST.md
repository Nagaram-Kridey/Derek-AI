# Derek — Implementation Checklist

Last updated: 2026-10-10 (Asia/Kolkata)

Status: **Implementation published; local and remote checks pass. Live setup and verification pending.** Backend, dashboard, companion, integrations and deployment configuration exist. Automated local tests, an isolated browser smoke check and GitHub Actions checks passed. Production operation has not been verified.

Legend: **Pending** · **In progress** · **Implemented** (code exists) · **Verified** (named checks passed). An implemented feature is not automatically a verified feature.

## Build and verification

| Phase | Work | Status | Evidence / remaining work |
|---|---|---|---|
| Foundation | Django configuration, models, migrations, typed contracts | Verified locally | Django check and migration consistency check passed; local migrations applied |
| Foundation | Authentication, turn API, history, audit and usage limits | Verified locally | Tests cover auth, isolation, mocked Gemini tool dispatch, history and daily budget enforcement |
| Research | Gemini grounded search and Semantic Scholar | Implemented | Mocked Gemini/research tests pass; live provider credentials pending |
| Research | Evidence verification and DOCX/PDF reports | Verified locally | Evidence/domain tests, generated DOCX/PDF and private PDF download/deletion tests pass |
| Scheduling | One-off/daily/weekly jobs, retry safety, timezone | Verified locally | Frozen-clock scheduling and duplicate prevention tests pass; continuous Redis/Celery runtime pending |
| Calendar | OAuth and owned-calendar read/create/update | Verified with mocks | One-use OAuth state, encrypted credential storage and scope checks pass; real authorization pending |
| Telegram | Approved-chat text/voice, reminders and reports | Implemented | Webhook secret/chat allowlist/update deduplication tests pass; live bot delivery/voice pending |
| Desktop | Paired-device queue, checkpoints and offline recovery | Verified locally | Device lease, expiry, replay prevention and journal tests pass; paired real PC runtime pending |
| Desktop | Folder/domain allowlists and sensitive-action approvals | Verified locally | Traversal/symlink/private-network checks and mocked browser approval/challenge tests pass |
| Interfaces | React dashboard | Verified locally | Production build, 2 API tests and isolated browser smoke check passed across all five pages |
| Interfaces | Desktop push-to-talk and speech output | Implemented | CLI help works; optional audio packages, microphone, Whisper model and Cartesia access pending |
| Release | Docker and AWS configuration | Validated statically | Terraform validate and local/production Compose config checks pass; actual containers/AWS not started |
| Release | Automated checks and local integration flow | Verified locally | 44 Python tests, 2 frontend tests, TypeScript/Vite build and Ruff undefined/unused checks pass |
| Release | Live provider and AWS verification | Pending | Requires user account setup below; Docker engine is stopped and AWS credentials are absent |

## Expected v1 features

Checked items have local verification evidence. Provider-dependent items remain unchecked until live checks succeed, even though their implementation is present.

- [x] Conversation persistence, export/delete controls and mocked assistant turns.
- [ ] Current internet research with citations and explicit unverified findings.
- [x] Generated DOCX/PDF report files and authenticated downloads; academic search live verification pending.
- [x] One-off, daily and weekly scheduling; Asia/Kolkata default timezone (automated verification).
- [ ] Google Calendar event read/create/update.
- [x] Draft/review/enable workflow lifecycle with scoped tools, sites and folders.
- [x] Global/workflow pause, cancellation, execution logs and sensitive-action approval contracts.
- [x] File and browser policy/checkpoint behavior in temporary-file and mock-browser tests.
- [ ] Desktop push-to-talk and Telegram text/voice notes.
- [x] Offline desktop queue and expiry/replay safeguards (local API tests); live continuous delivery pending.

## User setup (never paste secrets into this document or chat)

- [x] Local `.env`, generated development/encryption keys, dependencies, migrations and owner account are ready. Current username: `Kridey`.
- [ ] Configure Gemini API key, model access and daily usage limits.
- [ ] Enable Google Calendar API; configure OAuth client/secret/redirect URI; authorize account.
- [ ] Create Telegram bot, configure token, allowed chat ID and webhook secret.
- [ ] Configure Cartesia API key and licensed voice ID for speech output.
- [ ] Prepare AWS account, region and budget; supply deployment access through standard AWS credentials.
- [ ] Configure a domain/HTTPS endpoint for production OAuth and Telegram webhooks.
- [ ] Pair the Windows device, approve folders and sign into the assistant browser profile manually.
- [ ] Choose initial workflows and review their triggers and permitted actions before enabling.
- [ ] Start Docker Desktop for container/Redis checks; install the optional companion browser/audio dependencies.
- [x] Published the project to `https://github.com/Nagaram-Kridey/Derek-AI` on `main`, preserving the initial repository history. Local `origin/main` matches the implementation commit; GitHub Actions was triggered and its remote result is tracked separately.

## Verification record

| Check | Result |
|---|---|
| `python -m pytest` | 44 passed; source-directory warnings are expected before Docker assembles static assets |
| `npm test` | 2 passed: API credential confinement/auth errors and unsafe citation URLs |
| `npm run build` | TypeScript and Vite production bundle passed |
| `python backend/manage.py check` | No issues |
| `python backend/manage.py makemigrations --check --dry-run` | No changes detected |
| `ruff check backend companion --select F` | Passed |
| `terraform -chdir=infra/aws validate` | Configuration valid; no AWS resources created |
| `docker compose config --quiet` | Local configuration valid |
| Production Compose config with placeholder domain/image and `--no-env-resolution` | Valid; actual host env/secrets not validated |
| Local HTTP smoke | Dashboard returned 200; backend `/health/` returned `status: ok` |
| Browser smoke in disposable database | Login, draft save, Reports, Activity and Settings passed; no real credentials or website actions used |
| GitHub publication | Project published to `Nagaram-Kridey/Derek-AI` on `main`; Derek rename committed as `d3f8bfd`, with local and remote commit IDs verified |
| Remote GitHub Actions | Derek rename passed: backend tests against PostgreSQL, dashboard tests/production build, and Terraform validation on commit `d3f8bfd`. [Successful workflow run](https://github.com/Nagaram-Kridey/Derek-AI/actions/runs/38059196731) |
| Live Gemini/Calendar/Telegram/Cartesia, microphone, real websites, AWS | Not performed: account/hardware/deployment setup pending |

## Next actions

1. Complete the user setup checklist using `README.md` and `infra/aws/README.md`.
2. Start Redis, worker and Beat, then verify a real reminder reaches Telegram or Activity at its due time.
3. Verify a live Gemini answer, cited research report, Google Calendar event and local voice turn.
4. Pair the companion and test one approved folder and one reviewed website workflow; inspect approval/stop/reconnect behavior.
5. Review and apply AWS infrastructure, deploy the image, configure HTTPS/OAuth/webhook, and record live acceptance results here.

Known v1 limits: one app host; manual handling of MFA/CAPTCHAs and uncertain action outcomes; approved exact browser domains/targets only; one catch-up run after a recurring-schedule outage; source verification is automated evidence checking; S3 old versions and RDS backups have separate retention. No unrestricted shell, native Android, phone-call channel or multi-user access.

## Progress log

- 2026-10-10: Existing partial implementation inspected. Checklist created; continuation started. No live integrations or AWS deployment verified.
- 2026-10-10: Completed backend APIs/job dispatch, report exports, dashboard, companion CLI/voice, Docker, CI and AWS infrastructure. Fixed DRF download-format conflict discovered by integration testing and updated Cartesia request format against official documentation. Recorded local tests and browser verification. Live setup remains pending.
- 2026-10-10: Added detection of interrupted delivery/scheduler/Telegram jobs without automatic replay; final suite passed 44 Python tests. Temporary browser test account/database and owned preview servers were cleaned up. The real local database has migrations applied and awaits owner setup.
- 2026-10-10: Started the real local backend at `http://127.0.0.1:8000` and dashboard at `http://127.0.0.1:5173` on user request. HTTP/health checks passed. Created ignored `.env` with generated development/encryption keys; provider credentials remain empty. Owner account setup is pending (zero active owners). Background Redis/Celery workers are not running yet.
- 2026-10-10: Owner account is now present. Changed its username from `owner` to `Kridey` at the user's request and verified the saved value. Sign in using `Kridey` and the existing password; provider setup remains pending.
- 2026-10-10: Connected the local Git repository to `Nagaram-Kridey/Derek-AI`, retained the initial remote history and prepared the implementation for publication. Local credentials, databases, dependencies, generated reports, Terraform state and caches are excluded from Git.
- 2026-10-10: Pushed the implementation as commit `eef27cc656e1aa9c0d9931401a771f3032ec9aab` to `main` and verified the remote commit ID. A scan of the 90 tracked files confirmed local secret values and runtime data were excluded. GitHub Actions started for the published implementation.
- 2026-10-10: Remote PostgreSQL tests identified `FOR UPDATE` locking across nullable workflow joins. Restricted workflow-run and desktop-job locks to their own rows, preserving queue/approval behavior, and corrected the CI database health-check name. Follow-up local/remote checks are being run.
- 2026-10-10: Correction commit `f3ec21fb8001f3008415df479f75efb4a31c9118` passed all three GitHub Actions jobs. Local regression suite also passed all 44 Python tests. This final documentation-only status update skips a duplicate CI run; implementation verification is linked above. Local and remote `main` are synchronized after publication.
- 2026-10-10: Rebranded the assistant to `Derek` across dashboard branding/title/chat, model identity, companion CLI/voice, report/export names and current documentation. Verified the name on the running authenticated dashboard. Frontend tests/build, report export test, Django check, companion CLI help and Terraform validation passed; the backend was restarted to load the new identity. Configuration and persisted session/profile identifiers retain compatibility with existing installations. Published as `d3f8bfd91a6b13f4092122e8e0003f0527025606`; all three GitHub Actions jobs passed. This final checklist-only update skips duplicate CI.
