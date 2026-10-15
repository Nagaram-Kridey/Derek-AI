# Derek with a local model

## Current selection

Use **Ollama** with **qwen3:4b** on the Windows service PC. The model download is about 2.5 GB. It supports tool calling; actual speed and report quality depend on your hardware. After the user freed memory, the model loaded on CPU using about 3.8 GB. An authenticated greeting returned HTTP 200 with a clean final reply in 69 seconds after the response-filtering/no-thinking adjustment. The first five-project report completed, its four-page PDF was visually reviewed, and Telegram confirmed PDF delivery. Its evidence remains unverified; unsupported numerical proposal claims and overly broad MVP assumptions were corrected during setup review. Future reports should be treated as drafts requiring review.

The local adapter supports Ollama models with tool calling and JSON-schema output. A model that only chats may not run Derek's workflows or research planner. Cloud-tagged models and model metadata pointing to a remote host are rejected. Local mode does not fall back to Gemini.

## Configuration

The ignored `.env` selects the provider:

```dotenv
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=900
OLLAMA_NUM_CTX=8192
LILYLEO_TURN_TIMEOUT_SECONDS=1800
```

Gemini credentials can stay saved for later. They are not used for model generation or search while the selected provider is Ollama. Existing app usage limits still apply.

To change models, download a local tool-capable model, change `OLLAMA_MODEL`, and restart the backend and Celery worker. To return to Gemini, set `MODEL_PROVIDER=gemini` and restart those processes. Beat only needs restarting when its configuration changes.

## Start Ollama

If the Ollama desktop app/server is already running, use that server. Otherwise, from the project root in PowerShell:

```powershell
.\scripts\start-local-model.ps1
```

The script starts a loopback server with cloud features disabled and one model/request at a time. Keep that terminal open. Do not start a second server on the same port.

If the model has not been downloaded, use the installed Ollama executable (the installer may require reopening your terminal before `ollama` is on PATH):

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3:4b
```

Keep the backend, Redis, one Celery worker and one Beat scheduler running for daily automations. Settings shows the selected provider/model; “configured” does not confirm a model has loaded successfully. The existing 11 AM workflow remains a draft until reviewed and enabled.

## Internet research and voice

- Public search uses DDGS without a Gemini or search API key. Queries go to external search engines; retrieved pages are fetched through Derek's existing public-network restrictions. Search availability/rate limits can cause a report to fail.
- This is separate web retrieval, not Gemini Google Search grounding. Search snippets are explicitly unverified. Reports retain the independent-domain evidence checks; evidence that fails them remains unverified.
- To bound CPU work, local research uses one planned query and up to six result pages. Local answers and project suggestions may be less reliable than larger hosted models.
- Claims with fewer than two candidate source domains skip the local semantic model call and stay unverified; deterministic exact-quote checking still runs. A single source is not promoted to corroborated evidence.
- Planning, evidence judging, writing and five-project proposals use the selected local model. PDF/DOCX export, Telegram delivery, workflow approvals and browser/file scopes retain their existing behavior.
- Whisper transcription stays local. Speech output still uses the configured Cartesia cloud service; selecting a local language model does not change speech providers. Telegram also remains an external service.
- CPU requests can take minutes. If generation fails, free RAM or choose a smaller tool-capable model. Do not assume a timed-out task was replayed; inspect Reports/Activity before retrying.

This configuration expects Django and Ollama on the same Windows PC. An AWS instance cannot reach your PC's loopback address. The current loopback setup is not a complete Docker/cloud inference deployment.

## What you need to do next

1. Open `http://127.0.0.1:5173/` and sign in as `Kridey` with your existing password.
2. Keep the PC awake and leave Ollama, Django, Redis, one worker and one Beat scheduler running. Requests on this CPU can take minutes; avoid submitting several while a report is being generated.
3. Review the first completed report in **Reports**. A source marked unverified is not an established fact; project scores are model estimates.
4. Under **Automations**, inspect **Daily enterprise software and AI project ideas**, its steps and 11:00 Asia/Kolkata trigger, then select **Review & enable** when satisfied. Report delivery follows completion; it is not guaranteed at exactly 11:00.
5. Restart the desktop voice terminal before using voice so it picks up the longer local-model timeout. Speech output still requires Cartesia.

No additional model API key is required in local mode. Incoming Telegram commands still require public HTTPS/webhook setup; outbound report delivery uses the already configured bot/chat. Browser/file workflows separately require the companion process and approved domains/folders.

## References

- [Ollama chat API: tools and JSON schema output](https://docs.ollama.com/api/chat)
- [Qwen3 4B model](https://ollama.com/library/qwen3:4b)
- [Ollama FAQ: cloud controls](https://docs.ollama.com/faq)
- [DDGS public search library](https://github.com/deedy5/ddgs)
