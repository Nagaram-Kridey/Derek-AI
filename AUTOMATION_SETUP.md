# Derek — automations on this laptop

Updated: **2026-10-19 · Asia/Kolkata**

## Start the assistant

Open the **Derek** desktop shortcut or `Derek.vbs`. The managed local app starts the dashboard, scheduler, research/delivery workers and the paired desktop companion. **Docker and Redis are not needed in this mode.** Do not start a second Celery/Beat stack against the same database.

Open [the workspace](http://127.0.0.1:8000/). Today shows service health; Settings shows automation pause controls. Closing the workspace leaves the tray running. Local schedules, Telegram and browser/file work all require the laptop to stay awake. See [LOCAL_APP.md](LOCAL_APP.md) for startup/recovery commands.

## Your daily project-research routine

The existing **Daily enterprise software and AI project ideas** workflow is **reviewed and enabled**. Do not create another copy.

- **Trigger:** every day at **11:00 AM Asia/Kolkata**. Research starts then; delivery follows completion.
- **Scope:** enterprise software and AI. Only `research.run` is allowed; no browser account or local-folder permissions are needed.
- **Output:** five proposals with target users, problem hypotheses, MVP, evidence and a heuristic score. Two shortlisted ideas receive architecture, implementation stages and validation risks.
- **Ranking:** business value ×3 + feasibility ×3 + engineering depth ×2 + novelty ×2, maximum 50. Scores are model estimates, not validated demand.
- **Evidence:** claims without two independent supporting domains remain labeled unverified. Hypotheses and project designs are proposals. The latest completed report had no verified findings.
- **Freshness:** execution-date context and recent-title checks reduce exact repeats; semantic repetition is still possible.
- **Files:** read the report and download PDF/DOCX in Reports. New completed reports save a separate Telegram PDF-delivery intent. Unknown delivery outcomes need inspection before another copy is requested.
- **Current schedule:** next due **2026-10-19 at 11:00 AM**. One overdue scheduled occurrence completed as a catch-up at 01:31 IST on 2026-10-18, after a research-only cold-start retry. Another overdue run completed after the 2026-10-19 startup and its PDF delivery was accepted by Telegram. A punctual 11 AM run still needs observation.

Workflow ID: `a7401ae6-1640-4864-a8fc-bc9e38c42dd4`. Latest report: `fa72bc44-2f70-4cda-96ac-078ada8c0520`, completed at 01:51 IST on 2026-10-19. Both files exist, all five PDF pages were visually reviewed, and Telegram accepted the PDF delivery. DOCX visual review remains pending.

## Create or change a reminder

1. Open **Automations → New routine**.
2. Choose reminder or research, supply the message/topic, and choose once, daily or selected weekdays.
3. Review the displayed schedule; dates default to Asia/Kolkata.
4. Save. Use Edit, Pause/Resume and History on the routine card afterward.

A direct form save is your explicit instruction. Reminder/Calendar changes requested through chat or voice instead prepare an exact two-minute proposal: review and confirm that proposal. An unbound yes cannot approve an arbitrary pending action.

## Create or change a workflow

Describe the task, exact website/folder and timing in chat, or start from a template in Automations. A saved draft is not enabled automatically.

1. Inspect trigger, steps, allowed tools, folders and domains.
2. Choose **Review & enable** after reviewing the displayed definition.
3. Use **Run now** only when you intend an immediate execution; inspect Recent runs and Activity.
4. Pause the workflow to stop future execution, or cancel a specific queued/running run. Stop research in Reports to cancel its generation.

Editing a workflow disables it and cancels pending runs, so its new definition must be reviewed again. To change the existing 11 AM project routine, edit that workflow's trigger and re-enable it; do not edit its generated schedule separately.

## Browser and file workflows

The paired companion starts with the local app when its existing device credential is configured. Files must be in reviewed approved folders. Assistant source/state/credentials and browser-profile folders are protected. Browser domains and targets must be reviewed; MFA, CAPTCHA and unexpected pages pause for manual attention.

For manual website sign-in, quit the local runtime after current work first, then use the existing login helper:

```powershell
.\.venv\Scripts\python.exe -m desktop stop
# Wait until desktop status shows stopped, then:
.\.venv\Scripts\python.exe -m companion login https://YOUR_APPROVED_SITE
```

Finish manual sign-in, close all Derek login-profile windows, then reopen the desktop shortcut. The current browser channel is installed Chrome with a separate Derek profile. Simple YouTube navigation has prior evidence; full approved workflows and recovery still need live acceptance. See the browser setup section in [README.md](README.md).

## Delivery, pause and uncertain outcomes

The local Telegram poller needs the configured bot and approved private identity, without public HTTPS. It never removes a webhook or competes silently with another receiver. Cloud cutover will use one HTTPS receiver instead. Incoming conversation/voice acceptance remains pending.

Notifications also stay in the dashboard. Reports shows the last PDF-delivery state and offers an explicitly confirmed **Send PDF to Telegram** action. An uncertain send is not automatically repeated; inspect the actual chat before requesting another copy.

Settings → Pause all stops new automation dispatch. Current external actions may already have committed; stopping a reply is not an undo. Purchases, payments, account-security changes and permanent deletion require their specific approval. Inspect saved actions and Activity before retrying an uncertain outcome.

Earlier Docker recovery, failed Gemini previews and the original disabled-draft setup are historical. Current implementation and dated evidence: [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md).
