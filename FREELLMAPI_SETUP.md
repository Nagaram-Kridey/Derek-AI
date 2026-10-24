# FreeLLMAPI with Derek

Updated: 2026-10-20 · Asia/Kolkata

## Status

Derek supports `MODEL_PROVIDER=freellmapi` through the router's OpenAI-compatible chat-completions API. It supports typed tool calls, structured research generation, public web search, usage accounting, cancellation, Telegram and desktop/web conversations. Model inference does not execute tools: Derek validates tools and permissions and retains exact confirmation controls.

**Active router: http://127.0.0.1:3001**, using the owner's updated ignored `.env`. Authenticated model listing and live hosted inference passed. Derek uses `auto:fast` for interactive chat/tools/search synthesis and `auto:smart` for structured research operations. Exact models vary across the enabled router pool; sampled requests used Google, Kilo, Agnes and Groq. No provider keys or accounts were created by these checks.

Live Derek chat, cited search, exact reminder proposal/cancellation, Telegram-style preview and structured research planning passed. No Telegram test message was sent and no reminder task was created. Complete reports and live voice remain separate acceptance work. [Model roles, context, storage and evidence](DEREK_MODEL_AND_DATA_FLOW.md).

The previously installed official v0.16.5 portable app under `.tools/freellmapi-0.16.5` is a separate port-31415 setup, with a local Ollama endpoint. Optional `DEREK_FREELLMAPI_DESKTOP_AUTOSTART` applies only to that known port-31415 setup; it does not manage the active port-3001 server. Keep the port-3001 router running. Shared task instructions are described in [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md).

## Connect your router

1. Install/start your own router using the [project's installation guide](https://github.com/tashfeenahmed/freellmapi). Its documented server endpoint is `http://localhost:3001/v1`; desktop installations may use a different port. Use the actual endpoint shown by your installation.
2. In the router, add your approved provider keys. Enable models that support **function tools and JSON-schema responses**. Create a restricted routing profile if you want a fixed provider set. `auto:fast` ranks enabled models by measured speed; this is not a guarantee of latency or feature compatibility. A pinned compatible model is easier to diagnose for research.
3. Copy the router's **unified API key** into your ignored `.env`. Do not put the key in Git, a URL, Telegram or this chat.

```dotenv
MODEL_PROVIDER=freellmapi
FREELLMAPI_BASE_URL=http://127.0.0.1:3001/v1
FREELLMAPI_API_KEY=your-unified-router-key
FREELLMAPI_MODEL=auto:fast
FREELLMAPI_RESEARCH_MODEL=auto:smart
FREELLMAPI_REASONING_EFFORT=none
FREELLMAPI_TIMEOUT_SECONDS=300
DEREK_FREELLMAPI_DESKTOP_AUTOSTART=false
```

4. Restart Derek from the tray. In Features, choose **Current installation** for new conversations. Existing conversations using Current installation follow the new configuration; conversations explicitly pinned to Gemini retain that selection. Existing queued/running requests are not automatically replayed.
5. Check a short text answer, a source-linked web question and a reminder proposal through both dashboard and Telegram. A real write must still wait for its exact confirmation. Then check a research report; schema support differs between models/providers.

The router runs separately; optional startup applies only to the known portable installation above and does not update it or supervise its crashes. Plain HTTP is allowed only on loopback; a remote router must use HTTPS. Redirects and environment proxies are disabled for inference. Errors exposed to chat omit provider response bodies and API credentials. Derek does not add automatic Gemini/Ollama fallback; FreeLLMAPI's own configured routing still applies.

## Rotate the temporary key

When you rotate the unified key in FreeLLMAPI, replace `FREELLMAPI_API_KEY` in Derek's `.env` and restart Derek. The managed launcher now rereads `.env` on restart rather than retaining the previous provider/key environment. Do not change the router's encryption key as a substitute for API-key rotation; stored provider credentials use that encryption key.

To return to local inference, set `MODEL_PROVIDER=ollama` and restart Derek. Private desktop chat continues to use its separate local Ollama path regardless of the installation provider.

## Privacy, quotas and behavior

The router is self-hosted, but inference can go to enabled upstream providers. Their data policies, keys, rate limits and service availability apply. Router fallback may change the actual model/provider between calls, even when Derek's conversation keeps its configured `auto:fast` profile. Restrict enabled models/providers in the router if this is undesirable. Derek's health record groups calls by configured router profile, not the actual upstream model.

Public web search uses Derek's existing public-search connector, not automatic Gemini grounding through the router. Search snippets remain unverified evidence. Existing report evidence checks still apply. Voice transcription/output retain the currently configured Whisper/Cartesia setup; this adapter does not replace speech providers.

FreeLLMAPI describes itself as a personal experimentation project, with free tiers unsuitable as a supported production inference service. It is an optional inference route, not an unlimited free model or an availability guarantee. See the [project limitations](https://github.com/tashfeenahmed/freellmapi#disclaimer) and [API reference](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/api/01-rest-api.md).

## Faster model options researched

These are candidates, not benchmark results for this laptop. No replacement model was downloaded or selected.

| Candidate | Why consider it | Trade-off |
|---|---|---|
| [Ollama qwen3:1.7b](https://ollama.com/library/qwen3:1.7b) | Approximately 1.4 GB model download, smaller than the current 4B model; same model family/tool interface | Likely lower memory pressure; reasoning, tool arguments and report quality need comparison |
| [Ollama qwen3.5:2b](https://ollama.com/library/qwen3.5:2b) | Newer small model candidate; current tag approximately 2.7 GB | Requires compatible Ollama runtime and tool/JSON validation; parameter count alone does not predict speed |
| [Groq supported models](https://console.groq.com/docs/models) | Hosted inference removes this laptop's CPU bottleneck; inspect compatible models available to your account | Provider key, upstream privacy and actual quota/eligibility apply; advertised throughput is not end-to-end latency |
| [Cerebras catalog](https://inference-docs.cerebras.ai/models/overview) | Hosted low-latency inference candidate via the router | Model availability, tool/schema support and tier limits must be checked for your account |

For a fair next comparison, use the same short question, current-information question, reminder proposal and report with warm/cold timing; record correctness, total latency, RAM and failures. Keep action execution disabled until the exact proposal is reviewed. No benchmark or test messages were sent during implementation.
