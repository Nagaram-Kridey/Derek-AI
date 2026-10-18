# Derek — private local chat

Updated: 2026-10-18 (Asia/Kolkata)

Private mode uses a downloaded Ollama model, a separate local history database and, optionally, an installed Windows speech voice. It does not call Derek's online API, Gemini, Cartesia, public search, Telegram, Calendar or cloud tools. It does not synchronize history when the connection returns. Private chat is for conversation, explanations and drafts; it cannot schedule tasks or perform account actions.

## Open it

Choose **Private local chat** for text or **Private local voice** for the native voice window in the Windows tray. Close any online voice window before switching modes. The two modes share one microphone-session lock. For the console, run:

```powershell
.\.venv\Scripts\python.exe -m companion private
```

Optional speech:

```powershell
# Type and hear the reply through an installed Windows voice
.\.venv\Scripts\python.exe -m companion private --speak

# Local microphone recognition, local model, installed Windows voice
.\.venv\Scripts\python.exe -m companion private --voice
```

Private voice uses the same explicit Enter-to-arm, pause-to-finish, mute, idle timeout and lock controls as normal desktop voice. Voice capture requires the locally cached Whisper model; its initial model download needs internet. No recording files are created. Keep the model cached before expecting offline use.

## Controls and storage

In text mode: `/new` starts fresh context, `/history` displays the current conversation, `/conversations` lists saved conversations, and `/open NUMBER` returns to a listed conversation. `/export` writes the current one to the private exports folder; `/delete` asks for the literal word `DELETE` before removing it. `q` leaves. Ctrl+C interrupts an active local reply. Unfinished local prompts are recorded as interrupted; they are not silently replayed.

History is stored under the companion state directory in `private/history.sqlite3`; exports stay under `private/exports/`. This is separate from normal web/Telegram history and its online export/delete controls. The database and Markdown exports are ordinary local files protected by your Windows account's file permissions; they are not claimed to be encrypted. Deleting a conversation does not remove exports you previously created.

Only one private session can own that history at a time. The browser/file worker and the normal voice client use separate locks and state. A private conversation does not acquire their tools.

## Model and performance

`OLLAMA_BASE_URL` must be a loopback HTTP origin on this PC. Models marked remote/cloud are refused; private mode has no paid-provider fallback. The managed local app starts the installed Ollama server if one is needed, with cloud use disabled and one parallel generation. An already-running Ollama server is reused and is not stopped by Derek.

The existing CPU-only `qwen3:4b` setup previously needed 69 seconds for a greeting. Private mode bounds context/output, but that is not a promise of a fast reply. A smaller downloaded model may be more suitable when RAM is limited. No model download or new inference was required to implement this mode. Live text/voice acceptance and latency measurements remain pending.
