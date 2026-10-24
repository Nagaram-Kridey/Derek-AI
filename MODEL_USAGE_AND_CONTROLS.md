# Derek — answer quality and shared controls

Updated: **2026-10-20**

## Answer detail

Use **Features → Answer detail across chats** or send one of these in web chat or Telegram:

```text
/style auto
/style brief
/style balanced
/style detailed
```

The setting is stored for your owner account and applies to normal web, Telegram and online voice chats. An explicit request for a short or detailed answer wins. In adaptive mode, accepted reply-style memory can supply a preference; otherwise developed planning/architecture questions receive more space, and follow-ups can preserve the last answer's detail level. The model is instructed to stay on the same topic and ask when the referent is missing.

Default web answers have room for up to 1,536 output tokens; detailed answers up to 3,072. Telegram uses 320/1,024/2,048 for brief/balanced/detailed. These are ceilings, not required answer lengths or word counts. Structured action arguments retain at least 2,048 tokens of space so concise answer settings do not force incomplete workflow JSON. Online voice normally has a smaller text budget, while an explicitly detailed answer can include the full on-screen explanation after its short takeaway. Playback still uses the short spoken reply; exact action readbacks are never shortened.

Telegram bubbles remain at most 500 characters. Balanced answers can deliver up to ten bubbles before pointing to the complete dashboard reply. Explicit detailed answers and action readbacks are delivered in full through the ordered queue, with existing rate-limit and uncertain-send handling. Detailed answers can therefore take longer to generate and deliver.

## Context and accuracy

- Recent context stays within the selected conversation: up to 16 user/assistant messages and a 20,000-character recent-history budget, except the current request is retained intact. Older long messages are abridged with a visible marker rather than ending the context window immediately. Tool dumps and memory-management messages are excluded.
- Shared accepted personal memories remain a separate bounded lookup: up to five facts within 1,800 serialized characters. Private local history is excluded. Other channel transcripts are not automatically merged.
- Exact controls, supported common spoken schedules and supported built-ins avoid model inference. Ordinary questions send only read-tool declarations; action requests retain the validated write tools. This reduces unnecessary schema payload without adding permissions.
- Shared prompt version **2026-10-20.5** asks models to distinguish facts, inferences, estimates and proposals, preserve topic continuity, avoid invented chat details and state material uncertainty.
- Current factual claims still require web search when applicable. Search synthesis may cite only retrieved URLs; unsupported generated source links are removed. This link check does **not** prove every claim is supported. Full research retains its separate source-verification pipeline.
- Saved model replies include selected detail, context-message count and provider-call latency in milliseconds when available. Latency is for that inference call, not total queue, search, audio or delivery time.

FreeLLMAPI continues to use the configured interactive/research profiles. Gemini, Ollama and FreeLLMAPI share the instructions and server actions. Ollama's previous 1,024-token chat clamp is raised to 4,096 so it can honor the same requested budgets; larger local answers may be slower. No provider key, enabled provider pool, model weights or paid service was changed. These are application/prompt/context changes, not training on your chat history. Model quality still varies.

## Shared operational controls

Send `/controls` for the command guide. Natural-language requests also have access to the same registered inspection and control tools.

| Operation | Conversational access | Dashboard equivalent |
|---|---|---|
| Reminders/research schedules: create, inspect, update, pause/resume | Existing typed task tools; `/tasks` | Automations |
| Workflows: list/search/inspect | `/workflows`, `/workflow ID`, `inspect_workspace` | Workflow definitions |
| Review and enable workflow | `/enable ID`; full bound scope/action readback, then confirm | Review & enable |
| Pause/run workflow | `/pause-workflow ID`, `/run ID`; confirm | Pause / Run now |
| Edit workflow name, trigger, steps or permissions | Ask naturally with an exact ID/unique name; review the complete replacement and confirm. It saves disabled and requires review again | Workflow editor |
| Global pause/resume | `/pause-all`, `/resume-all`; confirm | Settings pause controls |
| Workflow run status/stop | `/runs`, `/run-status ID`, `/cancel-run ID`; stop requires confirmation | Recent runs |
| Research status/stop | `/reports`, `/report ID`, `/cancel-report ID`; stop requires confirmation | Reports |
| Request an additional PDF copy to approved Telegram chat | `/send-report ID`; confirm | Send PDF to Telegram |
| Sensitive step review/decision | `/approvals`, `/approval ID`, `/approve-step ID`, `/reject-step ID`; bound proposal confirmation | Approvals |
| Answer detail/model profile | `/style ...`, `/model configured` or `/model gemini`; model profile affects new conversations after `/new` | Features |
| Shared memory | Existing Remember/Forget/list commands; `/memory on|off`, `/suggestions on|off` | Settings → Memory |
| Account linking, device credentials, startup settings, bulk export/delete and memory pin/editor UI | Dashboard controls remain required | Settings |

Controls use owner-scoped records and the same operation handlers as dashboard actions. For workflows/reports, natural-language control calls may use a unique exact name; missing or duplicate names require an exact ID. No fuzzy target is executed. Lists are bounded; optional `query` searches names. The model must not guess IDs.

Telegram confirmations use the signed button attached to the exact readback. Bare Telegram yes is insufficient. Online voice requires completed playback of that proposal. Web chat uses its confirmation card/current exact proposal. Every approval binds the operation, target and reviewed state; changed targets require a fresh proposal. Sensitive step confirmation still rechecks the original risk, run, scope and checkpoint before resuming.

Global pause still blocks new active work, while resume, pause and cancellation controls remain usable. Pausing/stopping cannot undo an action already accepted externally. A queued run or PDF delivery is reported as queued, not completed. Reconfirming one committed proposal does not create a new effect.

Very large definitions cannot be reviewed completely in a short voice readback (800 characters) or a Telegram proposal (12,000 characters); use the full dashboard review for those cases. Some administrative/editor controls are still dashboard-only, as shown above. This is operational parity, not a claim that every UI feature is remotely exposed.

## Phone integration later

A future phone adapter should convert an authenticated call into the existing command/proposal protocol, read the exact proposal, collect its bound confirmation and deliver the saved result. Carrier/SIM availability alone does not provide a programmable voice gateway or authenticate a caller. Caller verification, call-session identity, replay protection, transport security and explicit account linking remain required. Phone support is still **not implemented**; no call forwarding or telephony configuration was changed.

## Current evidence and next work

Compilation, selected Ruff checks, Django system/migration consistency checks and dashboard production build are the implementation checks for this increment. The earlier 153 Python/8 dashboard test result predates these changes. No new automated tests, live model benchmark, Telegram send, workflow activation or sensitive action was performed for this increment.

Next acceptance work: compare brief/balanced/detailed answers and multi-turn relevance across configured models; exercise changed-target/replayed controls on each channel; check full Telegram delivery and pause/resume recovery. Add focused regression coverage when testing is requested. Phone and general Windows screen control remain separate milestones.
