"""Capability descriptions reflect configuration AND observed runtime state.

Reading this catalog never calls a provider or uploads user content.
"""

from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from . import models as m

META = {
    "inspect_workspace": ("Inspect workflows, runs and reports", "List exact IDs and inspect owner-scoped workflow definitions or saved outcomes from any online chat.", "cloud", "none", "none"),
    "control_workspace": ("Shared workspace controls", "Review and confirm workflow edits/enable/pause/run, global pause/resume, run/research cancellation, sensitive-step decisions and a Telegram PDF copy.", "cloud", "confirm", "none"),
    "search_web": (
        "Public web research",
        "Search current information with citations.",
        "cloud",
        "none",
        "model",
    ),
    "run_deep_research": (
        "Research reports",
        "Queue cited research and PDF/DOCX reports, including five project ideas narrowed to two.",
        "cloud",
        "none",
        "model",
    ),
    "schedule_task": (
        "Reminders and recurring research",
        "Prepare a one-off, daily or weekly task for your confirmation.",
        "cloud",
        "confirm",
        "scheduler",
    ),
    "list_tasks": (
        "Your scheduled tasks",
        "List reminders and recurring jobs with their next run time.",
        "cloud",
        "none",
        "none",
    ),
    "update_task": (
        "Change a scheduled task",
        "Review a reminder or research schedule change before saving it.",
        "cloud",
        "confirm",
        "scheduler",
    ),
    "set_task_enabled": (
        "Pause or resume a task",
        "Review a task pause or resume before applying it.",
        "cloud",
        "confirm",
        "scheduler",
    ),
    "calendar_list_events": (
        "Google Calendar",
        "Read events on your connected owned calendar.",
        "cloud",
        "none",
        "calendar",
    ),
    "calendar_create_event": (
        "Create a Calendar event",
        "Confirm an exact event and time before creation. Deletion is unavailable.",
        "cloud",
        "confirm",
        "calendar",
    ),
    "calendar_update_event": (
        "Update a Calendar event",
        "Review the target and change; stale event versions require a new review.",
        "cloud",
        "confirm",
        "calendar",
    ),
    "draft_workflow": (
        "Draft automations",
        "Draft scoped file, browser, Calendar and research workflows for review in Automations.",
        "cloud",
        "scope_review",
        "none",
    ),
}

MUTATIONS = {name for name, meta in META.items() if meta[3] == "confirm"}


def preferences(user):
    return m.AssistantPreferences.objects.get_or_create(user=user)[0]


def profile_details(user, profile):
    provider = "gemini" if profile == "gemini" else settings.MODEL_PROVIDER
    model = {"gemini": settings.GEMINI_MODEL, "ollama": settings.OLLAMA_MODEL,
             "freellmapi": settings.FREELLMAPI_MODEL}.get(provider, "")
    configured = (
        bool(settings.GEMINI_API_KEY and model)
        if provider == "gemini"
        else bool(model and settings.FREELLMAPI_BASE_URL and settings.FREELLMAPI_API_KEY)
        if provider == "freellmapi"
        else bool(model and settings.OLLAMA_BASE_URL)
    )
    status, reason = (
        ("unverified", "Configured; no recent successful provider call is recorded.")
        if configured
        else ("needs_setup", "Configure the model and its credentials first.")
    )
    health = m.ModelHealth.objects.filter(
        user=user, provider=provider, model_name=model
    ).first()
    if configured and health:
        if (
            health.last_failure_at
            and health.last_failure_at > timezone.now() - timedelta(minutes=30)
            and (
                not health.last_success_at
                or health.last_failure_at > health.last_success_at
            )
        ):
            status, reason = (
                "temporarily_unavailable",
                health.error or "The last provider request failed.",
            )
        elif (
            health.last_success_at
            and health.last_success_at > timezone.now() - timedelta(minutes=30)
        ):
            status, reason = "ready", "A provider request recently succeeded."
    usage = m.UsageDay.objects.filter(user=user, date=timezone.localdate()).first()
    if usage and (
        usage.model_calls >= settings.DAILY_MODEL_CALL_LIMIT
        or usage.input_chars >= settings.DAILY_INPUT_CHAR_LIMIT
    ):
        status, reason = (
            "quota_exhausted",
            "The application's daily model usage limit has been reached.",
        )
    return {
        "id": profile,
        "provider": provider,
        "model": model,
        "status": status,
        "reason": reason,
        "privacy": "Prompts are sent to Gemini."
        if provider == "gemini"
        else "Prompts pass through your FreeLLMAPI router to its enabled upstream providers; routing may change the served model."
        if provider == "freellmapi"
        else "Inference uses this server's Ollama installation; messages still pass through this service.",
    }


def catalog(user, profile=None):
    from .services import tool_contracts, state

    profile = profile or preferences(user).interactive_profile
    model = profile_details(user, profile)
    assistant_state = state(user)
    scheduler = bool(
        assistant_state.scheduler_heartbeat_at
        and assistant_state.scheduler_heartbeat_at
        > timezone.now() - timedelta(seconds=60)
    )
    desktop = m.DesktopDevice.objects.filter(
        user=user,
        revoked=False,
        last_seen_at__gt=timezone.now() - timedelta(seconds=60),
    ).exists()
    calendar_configured = bool(
        settings.GOOGLE_CLIENT_ID
        and settings.GOOGLE_CLIENT_SECRET
        and settings.CREDENTIAL_ENCRYPTION_KEY
    )
    calendar_connected = (
        calendar_configured
        and m.ProviderCredential.objects.filter(user=user, provider="google").exists()
    )
    rows = []
    for declaration in tool_contracts():
        name = declaration["name"]
        title, description, location, approval, dependency = META[name]
        if settings.LOCAL_EXECUTION and location == "cloud":
            location = "laptop"
        status, reason = "ready", "Available in the shared assistant."
        if dependency == "model":
            status, reason = model["status"], model["reason"]
        elif dependency == "calendar":
            status, reason = (
                ("unverified", "Connected; authorization will be checked when used.")
                if calendar_connected
                else ("needs_setup", "Connect Google Calendar in Settings.")
            )
        elif dependency == "scheduler" and not scheduler:
            reason = "Drafts can be saved; background delivery is waiting for a scheduler heartbeat."
        if assistant_state.paused and name != "control_workspace" and name in {
            *MUTATIONS,
            "run_deep_research",
            "draft_workflow",
        }:
            status, reason = "paused", "Automations are globally paused."
        rows.append(
            {
                "id": name,
                "title": title,
                "description": description,
                "location": location,
                "approval": approval,
                "status": status,
                "reason": reason,
                "implemented": True,
                "channels": ["web", "desktop_voice", "telegram"],
                "parameters": declaration["parameters"],
            }
        )
    rows.append({"id": "personal_memory", "title": "Shared personal memory",
                 "description": "Say Remember label: detail. Review suggestions, edit, pin, pause or forget in Settings → Memory. Accepted facts are shared across normal web, Telegram and voice conversations.",
                 "status": "ready" if preferences(user).memory_enabled else "paused",
                 "reason": "Local bounded lookup; private desktop history is excluded. No extra model call for memory retrieval.",
                 "location": "laptop" if settings.LOCAL_EXECUTION else "cloud", "approval": "owner_controls",
                 "implemented": True, "channels": ["web", "desktop_voice", "telegram"]})
    for name, title, description in [
        (
            "local_files",
            "Approved laptop files",
            "Runs only inside the folders of a reviewed workflow.",
        ),
        (
            "browser",
            "Signed-in browser workflows",
            "Uses a separate laptop profile and reviewed domains. Supports exact labels/button names, CSS targets, bounded waits, scrolling, reading and form actions; challenges pause execution.",
        ),
    ]:
        rows.append(
            {
                "id": name,
                "title": title,
                "description": description,
                "location": "laptop",
                "approval": "reviewed_workflow",
                "status": "paused"
                if assistant_state.paused
                else "ready"
                if desktop
                else "offline",
                "reason": "Automations are paused."
                if assistant_state.paused
                else "Device connected; each workflow must have approved scopes."
                if desktop
                else "Laptop companion is offline; queued work waits for reconnect.",
                "implemented": True,
                "channels": ["reviewed_workflow"],
            }
        )
    telegram_configured = bool(
        settings.TELEGRAM_BOT_TOKEN
        and settings.TELEGRAM_CHAT_ID
        and settings.TELEGRAM_USER_ID
        and (settings.LOCAL_EXECUTION or settings.TELEGRAM_WEBHOOK_SECRET)
    )
    telegram_receiver = None
    if settings.LOCAL_EXECUTION:
        from .local_status import runtime_status

        telegram_receiver = next(
            (
                row["status"]
                for row in runtime_status()["services"]
                if row["id"] == "telegram"
            ),
            "offline",
        )
    telegram_observed = m.TelegramUpdate.objects.filter(
        status="completed", created_at__gt=timezone.now() - timedelta(hours=24)
    ).exists()
    rows.append(
        {
            "id": "telegram",
            "title": "Telegram messages and voice notes",
            "description": "Private-chat conversations and short ordered replies; reports and reminders can be delivered here.",
            "location": "laptop" if settings.LOCAL_EXECUTION else "cloud",
            "approval": "setup",
            "status": "ready"
            if telegram_configured and telegram_observed
            else "unverified"
            if telegram_configured
            else "needs_setup",
            "reason": "A private update was recently processed."
            if telegram_configured and telegram_observed
            else f"Local receiver: {telegram_receiver.replace('_', ' ')}. Incoming conversation acceptance is still pending; no public webhook is needed for this mode."
            if telegram_configured and settings.LOCAL_EXECUTION
            else "Credentials configured; public HTTPS webhook registration and incoming delivery still require verification."
            if telegram_configured
            else "Configure the bot and approved private identity; cloud webhook mode also needs a webhook secret.",
            "implemented": True,
            "channels": ["telegram"],
        }
    )
    speech_configured = bool(settings.CARTESIA_API_KEY and settings.CARTESIA_VOICE_ID)
    rows.append(
        {
            "id": "desktop_voice",
            "title": "Desktop voice sessions",
            "description": "The native voice window and console use local speech-end detection, warm Whisper, streamed speech playback, stop/recovery controls and complete action readbacks. Ctrl+Alt+Space opens the voice window; Listen explicitly arms capture. Wake word remains planned; live voice acceptance is pending.",
            "location": "laptop",
            "approval": "setup",
            "status": "unverified" if speech_configured else "needs_setup",
            "reason": "Speech credentials configured; open voice from Chat or the Windows tray and complete live acceptance."
            if speech_configured
            else "Configure speech credentials and the companion voice dependencies.",
            "implemented": True,
            "channels": ["desktop_voice"],
        }
    )
    rows.append(
        {
            "id": "installed_app",
            "title": "Local Windows launcher",
            "description": "A Windows tray launcher serves the built dashboard, supervises local database workers, supports explicit voice launch and can opt into Windows sign-in startup. No Docker/Redis is needed in managed local mode. A signed standalone installer remains planned.",
            "location": "laptop",
            "approval": "setup",
            "status": "unverified",
            "reason": "Local launcher code is implemented; reboot/sleep/recovery acceptance remains pending.",
            "implemented": True,
            "channels": ["desktop"],
        }
    )
    rows.append(
        {
            "id": "private_local_chat",
            "title": "Private local chat",
            "description": "Explicit local Ollama text or voice chat with separate PC-only history and an installed Windows voice. No internet, cloud account tools, scheduling or automatic history sync is available in this mode.",
            "location": "laptop",
            "approval": "setup",
            "status": "unverified",
            "reason": "Launch from the tray or companion private command. An installed local Ollama model and enough RAM are required.",
            "implemented": True,
            "channels": ["desktop"],
        }
    )
    rows.append({'id':'desktop_observation','title':'Local screen observation preview',
        'description':'Open Settings → Screen observation or the local tray to select one app and approve a two-minute local UI Automation preview. Read-only control names and bounds stay local; no screenshots, input, model access or Telegram screen access. Known browsers/sensitive apps and elevated windows are excluded.',
        'implemented':True,'channels':['desktop'],'location':'laptop','approval':'local_consent',
        'status':'unverified' if settings.LOCAL_EXECUTION else 'needs_setup',
        'reason':'Read-only local preview implemented; native per-app acceptance pending. This is not a model tool or general desktop control.'})
    for name, title, reason in [
        (
            "desktop_screen_control",
            "Windows screen control",
            "Planned: opt-in per-app Windows UI Automation with fresh observations, scoped actions and a local stop control. Current browser workflows do not grant arbitrary desktop access.",
        ),
        (
            "wake_word",
            "Wake word",
            "Planned: an optional local wake word. Current voice sessions are armed explicitly from the voice window or console.",
        ),
        (
            "phone",
            "Call Derek",
            "Planned: forward the spare Airtel number to an approved Indian voice gateway; carrier plan, destination support and provider setup require confirmation.",
        ),
    ]:
        rows.append(
            {
                "id": name,
                "title": title,
                "description": reason,
                "location": "laptop" if name != "phone" else "cloud",
                "approval": "setup",
                "status": "not_implemented",
                "reason": reason,
                "implemented": False,
                "channels": [],
            }
        )
    return {"profile": model, "scheduler_online": scheduler, "capabilities": rows}


def model_tools(user, profile):
    from .services import tool_contracts

    rows = {row["id"]: row for row in catalog(user, profile)["capabilities"]}
    return [
        item
        for item in tool_contracts()
        if rows[item["name"]]["status"]
        not in {"needs_setup", "paused", "offline", "not_implemented"}
    ]


def system_context(user, profile, input_mode, channel):
    from .prompt_templates import CHANNELS, VERSION
    rows = catalog(user, profile)["capabilities"]
    descriptions = "\n".join(
        f"{row['title']} ({row['id']}): {row['status']}. " + (row['reason'] if row['status'] not in {'ready', 'unverified'} else '')
        for row in rows
    )
    style = CHANNELS["voice" if input_mode == "voice" and channel != "telegram" else channel]
    return (
        f"Derek instruction version {VERSION}. This runtime capability catalog is authoritative; distinguish planned, unconfigured and offline features. "
        "All state changes require server validation. Reminder and Calendar mutations create proposals, not completed actions. "
        "Use only exposed tools. Never claim a queued action completed or activate a workflow without its exact confirmed scope review. A model cannot grant permissions. "
        "Ask for AM/PM or the exact target when ambiguous. Model confidence cannot authorize a write. "
        "Answer general knowledge, brainstorming and suggestions naturally. For current facts, news, prices, availability, product comparisons, recommendations or explicit internet research, use search_web before answering. "
        "Never say you cannot access the internet when search_web is exposed. If search fails, say so and distinguish general knowledge from current evidence. Cite actual returned URLs; never invent sources or claim snippets are verified page contents. "
        + style
        + "\n"
        + descriptions
    )
