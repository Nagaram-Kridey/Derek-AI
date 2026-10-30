# Derek current acceptance status

Updated 29 October 2026, Asia/Kolkata. This is the current acceptance summary; older checklist entries are historical evidence. Implemented means code exists, not production acceptance.

| Area | Implemented | Tested in isolation | Verified live this batch | Remaining blocker |
|---|---|---|---|---|
| Shared command lifecycle | Yes | Request deduplication, confirmation binding, cancellation, channel formatting | Voice-transcript reminder saved once; duplicate request/confirmation reused IDs; two-turn web context passed | Actual microphone/speech path and human Telegram inbound acceptance |
| Reminders | Yes | Scheduling/timezone, once-only dispatch | Test reminder completed one occurrence and Telegram notification recorded sent | Extended scheduler soak and sleep/resume |
| WhatsApp one-time sending | Yes | DOM receipts, draft preservation, journal replay protection | No external test message sent in this batch | Next genuine message for full receipt-to-Telegram acceptance |
| WhatsApp monitoring/direct sending | Incomplete, disabled | Endpoint refusal and schema-independent ordinary routing | No watcher or acknowledgement enabled | Core acceptance first; saved preference is not active permission |
| Models/context | Yes | Reply depth, context and synthetic scoring | Benchmarks executed; see results below | Passing current route, repeat runs and factual-accuracy review |
| Research/reports | Yes | Integrated synthetic five-idea/two-shortlist pipeline, evidence labels and authenticated PDF/DOCX downloads | Historical reports are not a fresh research acceptance | Fresh five-idea/two-shortlist run on a passing provider |
| Local runtime | Yes | Worker recovery and startup regressions | Managed startup; backend/companion/Telegram fresh | Actual reboot/sign-in, sleep/resume and extended soak |
| Recovery | Yes | Isolated archive/restore and pre-migration safeguards | Normal startup applied migration 0014; latest encrypted archive verification succeeded | Off-device recovery and reviewed disaster cutover |
| Dashboard | Yes | Nine JS tests and Settings rendering checks passed | Backend started; full browser walkthrough pending | Current browser usability acceptance |

## Stabilization decisions

- Ordinary chat and job claims do not query or poll experimental WhatsApp monitoring. Exact one-time sending still requires confirmation.
- Dormant settings/watch tables were migrated through normal supervisor preparation, which verifies an encrypted archive before pending migrations. No live database was overwritten.
- Future messaging preferences remain: send on a clear request, watch requested contacts until stopped, acknowledge once with Noted. They are deferred, not enabled.
- Cloud, phone, extensions and broader desktop control wait until core reliability acceptance.
- No route changes based solely on speed. A candidate must pass all synthetic cases before recommendation; these checks do not prove general factual accuracy.

## Model evidence

Initial configured FreeLLMAPI test: four provider failures, median about 2.06 seconds; no passing recommendation. Owner-requested retry: arithmetic passed at 3.98s and context at 2.00s; the uncertainty sample failed the initial lexical check, while an additional sample correctly refused to invent a meeting time. Expanded scoring accepts common refusal wording. Detailed explanation failed at the 60s transport deadline. Retry median 3.30s includes failed samples and must not be presented as a successful response SLA. Ollama qwen3:4b: all four calls failed, median 70.07s. No candidate passed the entire benchmark, so provider settings remain unchanged (FreeLLMAPI).

Live shared web command acceptance: d4994cdf-5e38-41fc-85a8-e5d5d9552445 and 9aeaeb14-010f-4850-a218-275294818d89 completed with correct budget/follow-up totals at 3.05s and 3.02s; follow-up used three context messages. Saved answer forwarded twice to Telegram through its idempotent endpoint, with no model/tool rerun. Exactly one 70-character delivery row was recorded sent after both forwarding requests.

Reminder evidence: voice-transcript command 65c8ec43-5823-41a4-aa06-16c7d3fb5f35 saved task 2fe1a41c-67c2-4ec7-bd9d-b1b0a2284c86. Repeated request and exact confirmation reused IDs. One occurrence completed and notification 741bcd6e-3692-4725-bf03-b0b16561d15c was recorded sent. This tests the transcript/API path, not microphone recognition or speech output.

Repeat synthetic checks without dispatching tools or sending messages:

```powershell
# Run through the configured Django environment; user 1 is this installation's owner.
.\.venv\Scripts\python.exe backend/manage.py evaluate_models --user-id 1 --provider freellmapi --repeat 2 --output .companion/evaluations/latest.json
```

The management command uses the existing provider adapter and usage budget. It sends synthetic text only, reports metrics without raw provider errors, and never changes model preferences automatically.

## Next acceptance sequence

1. Passing configured model route and repeated context/accuracy samples.
2. Fresh daily project-research report with five proposals, two shortlisted, labels and downloads.
3. Actual voice and owner Telegram inbound checks.
4. Sleep/resume and reboot/sign-in checks with owner participation; recovery drill to a new isolated directory.
5. Resume messaging expansion only after these gates are recorded.

## Final verification for this batch

- Full Python suite: **296 passed, 1 optional browser test skipped**. Includes isolated report pipeline, command/channel, scheduling, replay protection, runtime/recovery and experimental-monitor isolation checks.
- Dashboard: **9 tests passed**, plus actual Settings startup-control rendering checks.
- Selected Ruff checks and migration consistency check passed. Managed services returned fresh ready states after restart; supervisor running.
- Live web context and reminder/Telegram evidence above are API-level checks. They do not establish microphone recognition, a human Telegram inbound conversation, general factual accuracy, full browser walkthrough, actual reboot/sleep or a fresh live research run.
- No WhatsApp recipient was messaged during stabilization. No monitoring or direct-send permission was enabled. No Git push performed.

## Model diagnostic reliability — 30 October 2026

Added bounded word-count/concept diagnostics and flushed per-sample benchmark checkpoints, so interruptions retain completed measurements without raw replies or credentials. Seven focused regression tests passed, including interruption recovery and diagnostic privacy. The previously completed eight-sample FreeLLMAPI run passed six arithmetic/context/uncertainty samples; both explanation samples failed (quality gate and 60-second timeout). This is historical benchmark evidence, not a current live-route acceptance. A fresh diagnostic run remains required; provider settings are unchanged.
