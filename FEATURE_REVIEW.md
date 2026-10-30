# Derek feature review — 29 October 2026

This is a recommendation record from independent red-team and blue-team review, not a feature-removal operation or new acceptance claim. It covers all 37 items in `backend/assistant/roadmap_seed.json`. [ACCEPTANCE_STATUS.md](ACCEPTANCE_STATUS.md) remains the authoritative current evidence summary. No owner board, saved task, history, permission or provider setting is changed by this document.

## Debate and decision

The red team argued that nine navigation destinations make a single-user assistant feel like an administration console. Duplicate history surfaces, marketing copy, and controls that appear to execute tests obscure whether a request actually completed. A heartbeat proves connectivity, not task readiness. The red team proposed a smaller daily interface and deferring expansion until core acceptance.

The blue team argued that later scope was frequently an explicit owner request, not accidental invention. Memory, private local chat, files, browser actions and one-time WhatsApp sends have practical value. Removing them merely to match the original lean plan would discard useful work. The better trade-off is to preserve implementations while making optional capabilities secondary and readiness explicit.

Both teams agreed to simplify navigation rather than delete functionality. Keep a compact Today summary for due work, review requests, failures and recent reports. Center daily use on chat, tasks and reports; group command history and activity under History while preserving their distinct records. Put connection/capability detail in Settings or contextual help. Preserve the owner-requested roadmap editor as a secondary planning tool.

Retire duplicate navigation, ornamental marketing sections and misleading test-executor language. Do not retire audit history, data, provider adapters or existing safety controls. Rename planning actions to describe their actual effect: marking a test planned is not running it. A manually entered passed result is owner-recorded evidence, not automated verification.

## Full inventory recommendations

**Keep** means maintain and complete acceptance. **Simplify** means reduce interface or configuration burden while retaining the capability. **Defer** means preserve the idea and dependencies without starting expansion. **Retire from active scope** means archive the proposal, not delete code or data. These recommendations do not replace implementation statuses.

| ID | Recommendation | Daily value and boundary |
|---|---|---|
| foundation | Keep | Saved commands, identity and audit are prerequisites for trustworthy actions. |
| dashboard | Simplify | Make requesting work and checking outcomes the primary flow. Preserve existing controls. |
| models | Simplify | Retain provider interfaces; foreground the selected route and honest availability, not a model catalog. |
| context | Keep | Relevant follow-ups and appropriate answer depth address repeated owner complaints. |
| memory | Keep | Cross-channel accepted facts prevent repeated explanations; retain correction and forgetting. |
| research | Keep | Internet research is an original daily use case; unsupported findings must remain labeled. |
| reports | Keep | Useful downloadable results are part of the original goal, not presentation overhead. |
| schedule | Keep | Saved, once-only reminders are a core assistant responsibility. |
| daily-projects | Keep | The requested five ideas/two shortlisted projects is the concrete research acceptance scenario. |
| calendar | Defer | Useful narrow connector after OAuth and core acceptance; prioritize ahead of broad desktop control. |
| workflows | Simplify | Show trigger, scope, review and outcome clearly; retain approval invalidation and pause controls. |
| files | Simplify | Keep approved-folder actions; avoid a general system administration surface. |
| browser | Simplify | Keep scoped semantic workflows and manual sign-in; make transport details secondary. |
| telegram | Keep | Essential phone access and notifications; complete concise bubbles and truthful outcomes matter. |
| voice | Keep | Original push-to-talk use case; real microphone, confirmation and playback acceptance is still needed. |
| private | Simplify | Preserve optional local-only mode and separate history; state that shared tools are unavailable. |
| runtime | Keep | Startup and reconnect reliability underpin an always-available laptop assistant. |
| autologin | Simplify | Reduce repeated local login friction without weakening website authentication or revocation. |
| observe | Defer | Preserve scoped observation work; further expansion waits for core and disposable-app acceptance. |
| mouse | Defer | Focus, stale screens and interruption require proven observation before broader control. |
| visual-agent | Defer | General screenshot-driven operation is expensive and unreliable without action/verification foundations. |
| streaming | Defer | First usability expansion after a passing model route; improve perceived latency without speaking unverified outcomes. |
| wakeword | Defer | Push-to-talk already meets the core need; continuous microphone work adds false wakes and resource use. |
| backup | Keep | Protect tasks, history and reports before migrations and updates; complete isolated recovery acceptance. |
| installer | Defer | Useful packaging later; runtime and reversible recovery must work first. |
| cloud | Defer | Can provide service while the laptop sleeps, but owner currently prioritizes the local product. |
| phone | Defer | Preserve the Airtel/A32 idea; gateway routing, identity, latency and costs remain unresolved. |
| custom-model | Defer | Training belongs to the separate project; integrate an endpoint only after task evaluations. |
| roadmap | Simplify | Preserve blocks, evidence and prompt export; label planning controls and keep them secondary. |
| evals | Keep | Repeatable quality and latency evidence is core stabilization work, not an optional distant extension. |
| sandbox | Defer | Existing isolated tests are useful now; a dashboard-executable test runner is a separate capability. |
| flags | Defer | Retain existing enforced pause controls; do not imply roadmap toggles control runtime behavior. |
| connectors | Defer | Select one concrete repeated need after Calendar and shared command acceptance; avoid a connector catalog. |
| mobile | Defer | Responsive web and Telegram cover current access; native clients add a separate maintenance burden. |
| multiuser | Retire from active scope | No present single-owner need justifies tenant/role complexity. Archive as a separate product idea. |
| browser-extension | Defer | Potentially useful selected-tab access, but it introduces permissions and pairing obligations. Preserve the plan. |
| whatsapp-web | Simplify | Preserve confirmed one-time sends and honest receipts; monitoring/direct-send expansion remains disabled. |

## Evidence caveats

- Implemented, tested in isolation, verified live and remaining blocker are separate dimensions. A source file or healthy worker is not a successful end-to-end user journey.
- The current acceptance summary records no provider passing the complete benchmark. Short successful replies do not establish detailed-answer reliability or factual accuracy.
- The synthetic benchmark exists, so the catalog's `evals: idea/later` classification is stale. It should be reconciled with current core acceptance work, without claiming full benchmark coverage.
- `daily-projects` is a current acceptance target despite its older catalog priority of later. Fresh live research with five candidates, two shortlisted projects and accessible reports remains pending.
- Actual microphone/speech use, human Telegram inbound conversation, reboot/sign-in, sleep/resume and extended soak remain unverified in the current summary.
- Existing WhatsApp evidence does not authorize a duplicate test send. Corrected receipt-to-Telegram acceptance waits for the next genuine requested message. Monitoring is incomplete and disabled.
- Private mode and long-term memory should remain distinct; do not imply local-only conversations enter shared memory.
- The owner-edited live board is separate from the seed. Catalog recommendations must not overwrite custom blocks, notes or evidence.
- This review does not certify the redesigned UI. Build, regression tests, keyboard/mobile layout and live browser walkthrough must be recorded separately after implementation.

## Delivery sequence

1. Finish the UI reorganization with accurate labels, empty/error states and preserved existing routes/actions; verify it without sending third-party messages.
2. Establish a passing model route with repeat context, detailed-answer and uncertainty samples. Keep latency and quality evidence together.
3. Complete a fresh project-research report and actual owner voice/Telegram acceptance; verify reminders save and deliver once.
4. Complete startup, sleep/resume and isolated recovery checks, with owner participation where required.
5. Accept existing scoped files/browser and genuine WhatsApp outcomes; only then reconsider monitoring. Calendar can follow consent and core acceptance.
6. Consider streaming before wake word, browser extension or broad desktop expansion. Cloud, telephone, custom training and native mobile remain optional later decisions.

The trade-off is a smaller daily surface with some advanced controls one level deeper. This preserves the owner's requested capabilities while making the assistant easier to use and its limitations easier to judge.
