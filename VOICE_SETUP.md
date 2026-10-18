# Derek — Desktop voice setup

Updated: 2026-10-18 (Asia/Kolkata)

Status: **Terminal and native-window voice implemented locally; live conversation, interruption and latency acceptance are pending.** Use Chat → Voice window, the tray, or Ctrl+Alt+Space to open the native window. Choose Listen to arm capture; Space starts/finishes/interrupts, Esc mutes. A Windows shortcut/launcher now runs the local app; a signed standalone installer, wake word and phone channel remain later work.

## 1. Start the local services

The desktop shortcut starts the built dashboard and local database workers without Docker or Redis. From the project folder in PowerShell:

```powershell
.\scripts\start-desktop.ps1
```

The existing daily research automation still needs the laptop awake. Cloud hosting has not been deployed.

## 2. Start voice

Install the companion dependencies if setting up another machine:

```powershell
.\.venv\Scripts\python.exe -m pip install -r companion/requirements.txt
```

The managed local app stores its desktop session token in Windows Credential Manager and refreshes it when you sign in. The existing `.env` user token is retained as a compatibility fallback; a device token only authorizes the browser/file worker. Cartesia and model settings still come from the ignored environment configuration. New conversations use the profile selected in Features, initially Gemini. Existing conversations retain their original profile. No automatic provider fallback occurs. The console remains available for setup:

```powershell
.\.venv\Scripts\python.exe -m companion voice
```

Whisper warms once at startup, downloading the configured model on first use if necessary. The microphone remains closed until Enter. There is no new API key required for local transcription. Online replies still depend on model quota and Cartesia availability; the current CPU-only Ollama model has previously taken 69 seconds for a greeting.

## 3. Controls

| Control | Behavior |
|---|---|
| Enter while idle | Open an active voice session. Speak after “Listening”. |
| Pause for about 0.9 seconds | Finish an utterance automatically. Whisper transcribes it locally. |
| Enter while recording | Finish the current utterance immediately. |
| Enter while thinking or speaking | Stop the current response, disarm its readback and request cancellation of unfinished work. Continue listening after the cancellation resolves. |
| `/mute` or `/stop` | Stop the response, request cancellation and close the microphone. Enter resumes explicitly. |
| `/retry` | Retrieve an unresolved command by its saved request ID, including after restarting the client. It never resends the original command. |
| `/new` | Start fresh conversation context after the prior request is resolved. |
| `/unmute` | Start a session from idle. |
| `q` | Close microphone/playback and leave. Uncertain requests retain their IDs for recovery. |

After a reply, follow-up speech uses the same conversation. The microphone closes during recognition, model work and playback by default. It closes after 30 seconds waiting for speech or five minutes in one active session. Windows lock detection pauses capture and playback; unlocking does not automatically resume listening. A second voice process using the same state directory is blocked while the browser/file worker can continue separately.

### Manual recording and device choices

For long pauses, increase `DEREK_VOICE_SILENCE_MS` in `.env` (450–3000 ms) or require Enter to finish each utterance:

```powershell
.\.venv\Scripts\python.exe -m companion voice --manual
```

List input/output devices without recording:

```powershell
.\.venv\Scripts\python.exe -m companion audio-devices
```

Set `DEREK_VOICE_INPUT_DEVICE` and `DEREK_VOICE_OUTPUT_DEVICE` to an index or name if the system defaults are unsuitable. Other bounded session settings are documented in `.env.example`.

### Spoken interruption — headphones only

```powershell
.\.venv\Scripts\python.exe -m companion voice --barge-in
```

This keeps the microphone open during playback. New speech stops playback and disarms any unfinished confirmation. It is off by default because echo cancellation is not implemented: speaker playback can otherwise trigger the detector. Enter remains the reliable interruption control. Wait for a cancellation to resolve before issuing another action; if it is unresolved, the client asks you to repeat rather than dispatching ahead of it.

## 4. Action confirmations

Reminder and Calendar changes produce an exact server readback, including the target and date/time/timezone. The full readback must finish playing before “confirm” or “cancel” is armed. Confirmation sends that proposal's ID, revision and digest directly; a bare voice “yes” cannot approve another proposal.

Interrupted, failed or expired readbacks are disarmed. Ask for the change again or use its dashboard confirmation card. Proposals expire two minutes after creation, so provider delays can leave less time to respond. Multiple proposals need separate dashboard review. A spoken confirmation already accepted by the server can finish even if you subsequently stop its reply; stopping does not undo a saved action. Inspect Activity if an outcome is uncertain.

## 5. Recovery, privacy and performance

- A lost API response retains conversation/request/command IDs in the existing local state directory. `/retry` reads the saved outcome; an unknown request returns an error and can be cleared with `/stop`. New commands wait until that request is resolved.
- Local audio is held in bounded memory, with no recording files. Whisper receives a local sample array; the recognized text goes to the assistant API and response text goes to Cartesia. Normal conversation history follows the existing history/export/delete controls. Private offline chat is a later feature.
- Playback uses bounded raw PCM chunks as Cartesia sends them. The model still completes its text response before synthesis starts; this is audio streaming, not model token streaming.
- The console shows recognition time, command response time and time to the first non-silent audio submitted to the output device, plus playback underruns. These timings contain no transcript/audio and are not written to a telemetry file. Full replies and transcripts are visible in the console.
- Cancellation marks a durable request ID, suppresses late tool dispatch/results and attempts to abort active Gemini/Ollama inference. A provider may still bill work already accepted. A running non-mutating public-search/Calendar read may finish its bounded network operation; saved actions and queued reports continue according to their recorded state.

## Live acceptance remaining

- [ ] Ordinary greeting and follow-up retain context and produce audible replies.
- [ ] Natural pauses and manual recording behave correctly with the selected microphone.
- [ ] Enter interruption, optional headphone interruption and a lost connection cannot approve a stale readback or duplicate an action.
- [ ] A real reminder readback requires fresh confirmation; the saved result appears once.
- [ ] Idle timeout, mute, Windows lock/unlock, audio-device failure and restart recovery behave correctly on this laptop.
- [ ] Measure representative warm Gemini latency; compare with the plan's targets before packaging.

Static compilation/lint and service startup do not satisfy these live acceptance items. No microphone recording, model inference, speech generation or new outbound message was initiated as part of implementing this prototype.
