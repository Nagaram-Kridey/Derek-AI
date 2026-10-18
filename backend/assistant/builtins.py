"""Small read-only answers that do not need model inference or network access."""

from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from . import models as m


def answer(command):
    text = command.input_text.casefold().strip().rstrip(".!?")
    if text == "/start":
        return f"Hi, {command.user.username}. I'm Derek. Send a message or voice note; use /help for features and /new for a fresh conversation. Changes need your exact confirmation."
    if text in {"hi", "hello", "hey", "hi derek", "hello derek", "hey derek"}:
        return f"Hi, {command.user.username}. What would you like a hand with?"
    if text in {"/time", "what time is it", "what's the time", "current time"}:
        return (
            timezone.localtime().strftime("It is %I:%M %p on %A, %d %B %Y")
            + f" ({settings.TIME_ZONE})."
        )
    if text in {"/date", "what's the date", "what is the date", "what day is it"}:
        return (
            timezone.localtime().strftime("Today is %A, %d %B %Y")
            + f" ({settings.TIME_ZONE})."
        )
    if text in {
        "/tasks",
        "list my tasks",
        "list my reminders",
        "show my reminders",
        "show my scheduled tasks",
    }:
        from .commands import _schedule_label

        tasks = m.ScheduledTask.objects.filter(user=command.user).order_by(
            "next_run_at"
        )[:30]
        return (
            "\n".join(
                f"- **{task.name}** — {'active' if task.enabled else 'inactive'}; {_schedule_label(task.schedule)}."
                for task in tasks
            )
            or "You have no scheduled routines yet. Add one in Automations, or ask me to prepare a reminder."
        )
    if text in {
        "/help",
        "help",
        "what can you do",
        "what can derek do",
        "show your features",
    }:
        from .capabilities import catalog

        data = catalog(command.user, command.model_profile)
        connected = [
            row["title"]
            for row in data["capabilities"]
            if row["implemented"]
            and row["status"]
            not in {"needs_setup", "not_implemented", "offline", "paused"}
        ]
        unavailable = [
            row["title"] + ": " + row["reason"]
            for row in data["capabilities"]
            if row["status"]
            in {
                "needs_setup",
                "offline",
                "paused",
                "temporarily_unavailable",
                "quota_exhausted",
            }
        ]
        result = "Here is what is implemented in this installation:\n\n" + "\n".join(
            "- " + title for title in dict.fromkeys(connected)
        )
        result += "\n\nSome connected features still need live acceptance. Reminder and Calendar changes need your exact confirmation; workflows need review before activation."
        if unavailable:
            result += "\n\n**Unavailable or waiting for setup**\n" + "\n".join(
                "- " + title for title in dict.fromkeys(unavailable)
            )
        result += "\n\nUse Features for current connection/model details. The phone gateway, wake word and signed installer are still planned. Quick commands: `/tasks`, `/time`, `/date`, `/status`."
        return result
    if text in {"/status", "assistant status", "are your services running"}:
        from .services import state
        from .local_status import runtime_status

        current = state(command.user)
        runtime = runtime_status()
        scheduler = (
            current.scheduler_heartbeat_at
            and current.scheduler_heartbeat_at > timezone.now() - timedelta(seconds=60)
        )
        return (
            f"The assistant is running in {'managed local' if runtime['managed'] else 'service'} mode. "
            f"Automations are {'paused' if current.paused else 'enabled'}, and the scheduler is {'online' if scheduler else 'waiting for a heartbeat'}. "
            "See Today for each service and Command history for saved outcomes. Local jobs require this laptop to stay awake."
        )
    return None
