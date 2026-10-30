# WhatsApp acceptance request — 2026-10-24

### Live search-only acceptance — 2026-10-27

Fixed post-click search OCR validation by using bounded exact full-window placeholder evidence when the caret corrupts the magnified reading. Added bounded re-observation. Recipient result selection now uses the dedicated Chats/Contacts section and stops before Groups in common or message search results. A live `python -m companion.whatsapp --find-recipient "MSV Krishna"` run typed the name, opened the exact chat, verified its header and returned recipient_verified=true, message_typed=false, message_sent=false. This validates navigation and search only; it does not establish autonomous send acceptance. Previously stopped Telegram runs were not replayed.

### Progress reporting — 2026-10-27

Direct chat sends now report opening, searching, recipient verification, draft verification and outgoing checks through fixed-stage authenticated device calls. Stages are deduplicated per run and delivered in order to the originating Telegram conversation, as well as saved to chat events/messages. Desktop completion produces a terminal reply: outgoing verified (not proof of delivery/read), or stopped with the saved reason. No failure triggers an automatic message replay. The last stopped run's missing terminal notice was queued explicitly during recovery. Search OCR now magnifies the sidebar text area; live search acceptance is still required.

## Current page workflow — 2026-10-27

### Direct requests in chat (preferred for one-time messages)

Say: `Send a WhatsApp message to MSV Krishna saying: Hello`.

Derek reads back the exact recipient and message. Confirm the current proposal to queue one desktop send, or cancel. The same tool uses the existing web, Telegram and voice proposal controls. Voice/Telegram require their exact proposal confirmation control; an unrelated text reply cannot approve an old proposal. No routine setup or schedule is required. The initial response means queued, not sent or delivered; inspect the run in Activity. Underlying durable desktop bookkeeping is excluded from the routine list and cannot be manually replayed. The Windows companion must be available, with WhatsApp signed in and Windows unlocked. Existing OCR uncertainty limitations still apply.

Verified with three isolated database tests: nothing queued before confirmation, one run after confirmation with no replay, cancellation without a run, and exclusion from the routine list. No real message was sent for these tests.

In Automations choose **WhatsApp message**, enter an exact contact name and a single-line message, then save for review. Review the workflow, enable it and run manually. Refresh the local page after deployment. The form sets `open_and_search=true` on `desktop.whatsapp`.

This option activates the registered Windows WhatsApp package, maximizes its window, searches the dedicated sidebar field, rejects duplicate or non-exact results, opens the matching conversation and applies the existing draft/send checks. It uses direct package activation instead of typing into Windows Search. Windows must be unlocked and WhatsApp already signed in. App focus refusal, unsupported layout, nonempty search, ambiguous results or OCR uncertainty require attention; no blind retries.

The new navigation path passed synthetic unit tests, not live end-to-end sending acceptance. The earlier assisted introduction remains the only verified introduction send. Punctuation/caret readback remains a known limitation. This is a narrow WhatsApp adapter; it does not grant arbitrary application input, Windows terminal control, or generic tab switching. Reply monitoring remains deferred.

Requested test: send a short test to the Draft group; command Derek to send the owner's exact introduction to MSV Krishna; watch that recipient for five minutes after sending and acknowledge a new reply once with `Noted`.

## Current evidence

- WhatsApp Desktop is installed, open and signed in. Draft is visible as a group.
- The computer-use inspector returns no accessibility tree for this WhatsApp version.
- Derek's own local preview was tested through its consent UI against WhatsApp. It returned window/pane metadata but no usable messaging controls.
- WhatsApp uses owned WebView child processes. The reader now recognizes only WhatsApp-owned WebView descendants, with process creation-time checks; standalone WebView processes cannot be approved as a browser-policy workaround.
- Allowing those descendants did not produce usable chat controls in the installed app. This is an observed compatibility limit, not successful messaging acceptance.

## Desktop implementation — owner choice confirmed

The owner selected WhatsApp Desktop with screen and mouse control. No Web QR pairing is required for this implementation path.

- Added optional local Windows OCR to the native preview, restricted to WhatsApp Desktop. Select the visual-reading checkbox before approving the window. Captures remain in memory; the existing killable worker, two-minute consent and STOP control still apply. Native capture compatibility remains to be accepted against the live app.
- Windows OCR recognized a generated English fixture locally. Two recipient-region tests and eleven message-guard tests pass, alongside sixteen existing observation tests.
- Added a pure message verification guard: exact composer and recipient checks, new outgoing anchor, five-minute monotonic deadline, two matching incoming observations, and at-most-once acknowledgement reservation. This guard is not yet connected to an input executor; it cannot independently prove that a visual bubble is incoming.
- Still needed: scope-bound mouse/keyboard adapter, durable send journal integration, verified recipient/composer/outgoing/incoming visual extraction, shared interaction locking, and end-to-end Derek command acceptance. No live send is enabled by these primitives.

Before sending, implement/accept exact recipient and group verification, explicit message readback, durable send checkpoints, and a five-minute reply watcher scoped only to MSV Krishna. A received reply is data, not authorization to change the message or perform other actions. `Noted` must be sent at most once and only for a new reply after the outgoing introduction, within the requested window. Sending/monitoring must pause on ambiguous recipients, sign-in challenges, changed state, uncertain send results, cancellation or scope loss.

## Actual delivery status

Update, 2026-10-26 (test crossed midnight locally): the exact introduction to MSV Krishna was sent once and visually verified as an outgoing bubble, with an empty composer afterward. Derek's registered `desktop.whatsapp` workflow typed the draft but stopped at exact OCR readback (small punctuation/caret artifacts). Codex visually verified the full requested wording and clicked Send through desktop control. This is assisted live acceptance, NOT successful autonomous Derek sending. The workflow was paused afterward and its uncertain journal was not cleared or marked automatically completed.

The Draft group test remains unsent. Reply checking and `Noted` are explicitly deferred by the owner's latest instruction; no watcher is running.

Implementation now includes typed manual single-message workflow contracts, foreground/scope/geometry and Escape checks, journal-before-typing, no uncertain replay, and an interaction lock shared with the browser worker. Local OCR uses a magnified composer region. Still required: robust exact punctuation/caret recognition, stronger focus and bubble verification across layouts/themes, autonomous end-to-end acceptance, and later reply monitoring. Earlier 'still needed/no connector' descriptions above are historical to the initial compatibility check.


## Autonomous acceptance — 2026-10-27

The composer caret failure was reproduced and fixed with exact-empty retry checks. The latest requested test was submitted and confirmed entirely through Derek APIs. Both attempts stopped before typing because Windows denied foreground activation; the second included the fixed-package launcher fallback. Final run: `5d005cf7-9300-4a5c-bd2e-46c023deda7d`, needs_attention. No Codex mouse/keyboard assistance was used after the latest instruction and no new send is claimed. Autonomous send acceptance remains incomplete. The existing historical assisted send is not counted as autonomous success.


## Preferred setup: dedicated Brave WhatsApp Web — 2026-10-27

New chat/Telegram/voice sends use the dedicated Brave Web profile automatically after exact confirmation. Other browser tasks retain their configured browser. No .env change is required. The profile is `%LOCALAPPDATA%\LilyLeo\whatsapp-brave-profile`, outside this project; cookies, IndexedDB and linked-device credentials stay local and are not included in project backups.

Open **Settings → Your local app → Open WhatsApp setup**, link manually from your phone, then close the dedicated Brave windows. The ordinary Brave profile remains separate. A busy profile produces an explicit pause rather than another browser instance or a session reset. Settings Check setup shows the last observed connection state; each send checks login again.

CLI equivalents:

- `.venv\Scripts\python.exe -m companion.whatsapp_web login`
- `.venv\Scripts\python.exe -m companion.whatsapp_web inspect` (reopens, checks login, closes; no message input)
- `.venv\Scripts\python.exe -m companion.whatsapp_web status`
- `.venv\Scripts\python.exe -m companion.whatsapp_web inspect-message --recipient "Exact contact name" --message "Exact text"` (existing-message inspection, no sending)

Use chat or Telegram: `Send a WhatsApp message to MSV Krishna saying: Your exact message`. Review the Brave WhatsApp Web proposal and confirm. The laptop must be awake, Windows unlocked and the setup browser closed. A missing login asks for relinking. Existing drafts, duplicate contacts, recipient changes, unexpected connections or uncertain sends stop execution. Do not repeat an uncertain send until the existing chat is checked.

Live test: Derek alone sent the authorized introduction at 11:32 on 27 October 2026. The initial outgoing-marker check failed and the job honestly remained needs_attention. The marker was corrected against the live DOM and a separate read-only check verified the new exact outgoing bubble and empty composer. No extra test copy was sent. A fresh send with the corrected final check is reserved for the next genuinely requested message. Delivery/read status and reply watching are not accepted by this test.

Session lifetime: keep using WhatsApp on the primary phone at least within 14 days; WhatsApp also documents logout of linked devices after 30 days of their own inactivity. Manual logout or session invalidation can require relinking earlier. These are inactivity rules, not a guaranteed permanent login. [Official linked-device guidance](https://faq.whatsapp.com/378279804439436/?cms_platform=android&locale=da_DK).
