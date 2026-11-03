# Connecting your own text model

Derek can use a separately hosted model through an OpenAI-compatible `/v1/chat/completions` endpoint. FreeLLMAPI remains the default until you configure a replacement. Training and hosting the model are separate tasks.

## Testing workspace

When your endpoint is ready, stop the trial and run:

```powershell
.\.venv\Scripts\python.exe -m testing_workspace stop
.\.venv\Scripts\python.exe -m testing_workspace llm-configure
.\.venv\Scripts\python.exe -m testing_workspace start --publish
```

Choose `custom`, enter the base URL ending in `/v1`, model identifier and API key at the hidden prompt. HTTPS is required except for loopback development endpoints. Remote endpoints require authentication. Enable tool calls or JSON schema only if your model server implements them. Reports requiring structured responses need JSON schema support.

Settings stay in the ignored private trial configuration. Do not paste API keys into chat, frontend code or Git. Images and speech retain their independent providers; changing the text model does not migrate them. No automatic provider fallback occurs. To return to the current text router, run the same command and choose `freellmapi`.

## Other runtimes

Server-side configuration supports `MODEL_PROVIDER=custom`, `CUSTOM_LLM_BASE_URL`, `CUSTOM_LLM_MODEL`, `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_TIMEOUT_SECONDS` (15–600 seconds), `CUSTOM_LLM_SUPPORTS_TOOLS` and `CUSTOM_LLM_SUPPORTS_JSON_SCHEMA`. Both capability switches default to false. Never expose the model credential to the browser.

Before inviting testers, verify a real response, conversation context, timeouts and any declared tool/schema capabilities against your server. A live custom-model test cannot be completed until that endpoint exists.
