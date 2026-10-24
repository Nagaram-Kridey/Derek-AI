# Derek task templates and model routing

Updated: 2026-10-20 · Asia/Kolkata

The authoritative instruction registry is `backend/assistant/prompt_templates.py`, version **2026-10-20.5**. It is application code, not text supplied by webpages or a model. Gemini, Ollama and FreeLLMAPI use the same base policy and shared research mixin. Accepted long-term memories enter as bounded untrusted personal data, never tool permissions; memory commands and owner controls are handled locally. Instructions now cover adaptive answer detail, topic continuity, uncertainty and the shared workspace-control tools. Browser instructions retain exact semantic targets, bounded waits/scrolling and approval requirements. See [MODEL_USAGE_AND_CONTROLS.md](MODEL_USAGE_AND_CONTROLS.md) and [MEMORY.md](MEMORY.md).

| Template | Used by |
|---|---|
| `SYSTEM` | All three inference adapters: identity, honest tool outcomes, untrusted data, exact approvals, timezone and abridged-context rules |
| `CHANNELS.web` | Dashboard answer style |
| `CHANNELS.telegram` | Telegram text and voice-note answers: concise paragraphs, main points first |
| `CHANNELS.voice` | Desktop voice: brief speech; exact server readbacks remain intact |
| `search_answer` | Tool-free synthesis of actual web-search evidence |
| `research_plan` | Focused public research queries |
| `verify_evidence` | Claim/source entailment, short exact evidence quotes and uncertainty |
| `project_ideas` | Five enterprise proposals, bounded MVPs, heuristic scores and supplied evidence references |
| `shortlist` | Two proposal numbers, score/tie constraints and allowed selection criteria |
| `report_summary` | Selection of existing finding IDs; factual prose is copied by the server |

`task_prompt` renders the named template with JSON labeled as untrusted task data. Unknown template IDs fail. Interactive replies record the instruction version in saved response metadata. A provider/router does not supply replacement application instructions or new executable tools.

## What remains enforced by code

- The runtime capability catalog and registered tool names determine availability.
- Tool argument contracts, owned resources and workflow folder/domain restrictions still apply.
- Writes require the exact server-generated proposal/revision/digest, with expiry and cancellation checks. Model-generated confirmation language does not authorize them.
- Action readbacks and committed outcomes use server wording; search-only synthesis cannot invoke tools.
- Report evidence checks, source domains, indices, ranking constraints and export generation remain in Derek.
- Command identity, replay handling, Telegram sender restrictions, ordered delivery and uncertain-outcome handling remain independent of inference.
- Private desktop chat stays on its separate local Ollama path and does not inherit cloud routing or assistant account tools.

These measures preserve task contracts and approval behavior across models. They cannot make different models equally accurate or guarantee identical wording. A new routed model must support function calling and the JSON outputs required for reports; incompatible responses fail with a clear error rather than executing unvalidated text. FreeLLMAPI's internal fallback can change the underlying provider; restrict its enabled models or pin a compatible model when reproducibility matters.

## Current route

`Derek (Current installation) → port-3001 FreeLLMAPI → enabled hosted model`

Interactive requests use `auto:fast`; schema-based research uses `auto:smart`. The owner's updated router configuration has hosted providers available. Live chat, cited search, reminder proposal/cancellation, structured planning and Telegram-style preview passed; full report/voice acceptance remains separate. Private chat stays local. See [DEREK_MODEL_AND_DATA_FLOW.md](DEREK_MODEL_AND_DATA_FLOW.md) for context/storage details and dated evidence.
