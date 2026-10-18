"""Local database queue runner: fixed typed work only, without Redis or Docker.

Cloud/Celery mode remains separate. Each lane has one advisory lock and its own
process. Running/uncertain records are never replayed after an interruption.
"""

import argparse
from datetime import datetime, timezone as dt_timezone
import logging
import os
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    parser = argparse.ArgumentParser(description="Derek local queue runner")
    parser.add_argument(
        "lane", choices=("interactive", "research", "delivery", "scheduler")
    )
    args = parser.parse_args()
    os.environ["DEREK_LOCAL_EXECUTION"] = "true"
    import django

    django.setup()
    from django.db import close_old_connections
    from django.db.models import Q
    from django.utils import timezone
    from assistant import models as m, tasks
    from companion.journal import WorkerLock
    from desktop.state import RUNTIME, write_record, read_record

    stop = threading.Event()
    state = {
        "status": "starting",
        "pid": os.getpid(),
        "mode": "local",
        "task": None,
        "task_started_at": None,
    }

    def interrupted(*_):
        stop.set()

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)

    def heartbeat():
        while not stop.is_set():
            try:
                write_record(args.lane, dict(state))
            except OSError:
                pass
            stop.wait(5)

    def next_job():
        if args.lane == "interactive":
            busy_conversations = m.Command.objects.filter(status="running").values(
                "conversation_id"
            )
            command = (
                m.Command.objects.filter(status="queued")
                .exclude(conversation_id__in=busy_conversations)
                .order_by("created_at")
                .first()
            )
            if command:
                return tasks.process_command, command.pk
            update = (
                m.TelegramUpdate.objects.filter(status="pending")
                .order_by("created_at")
                .first()
            )
            return (tasks.process_telegram, update.pk) if update else None
        if args.lane == "research":
            report = (
                m.Report.objects.filter(
                    status="queued", user__assistantstate__paused=False
                )
                .order_by("created_at")
                .first()
            )
            if report:
                return tasks.research_report, report.pk
            from assistant.services import run_allowed

            for run in (
                m.WorkflowRun.objects.filter(
                    status="queued", user__assistantstate__paused=False
                )
                .select_related("user", "workflow")
                .order_by("created_at")[:100]
            ):
                if run_allowed(run):
                    return tasks.execute_run, run.pk
            return None
        occurrence = (
            m.ScheduledOccurrence.objects.filter(
                status="pending", task__user__assistantstate__paused=False
            )
            .order_by("scheduled_for")
            .first()
        )
        if occurrence:
            return tasks.execute_occurrence, occurrence.pk
        notification = (
            m.Notification.objects.filter(status="pending")
            .order_by("created_at")
            .first()
        )
        if notification:
            return tasks.deliver_notification, notification.pk
        delivery = (
            m.Delivery.objects.filter(status="pending", due_at__lte=timezone.now())
            .order_by("due_at", "position")
            .first()
        )
        if delivery:
            return tasks.deliver_command, delivery.pk
        report = (
            m.Report.objects.filter(
                status="completed", progress__telegram_delivery__status="pending"
            )
            .filter(
                Q(progress__telegram_delivery__due_at__isnull=True)
                | Q(progress__telegram_delivery__due_at__lte=timezone.now().isoformat())
            )
            .order_by("created_at")
            .first()
        )
        return (tasks.send_report_file, report.pk) if report else None

    with WorkerLock(RUNTIME / (args.lane + "-lock")):
        threading.Thread(target=heartbeat, daemon=True).start()
        state["status"] = "ready"
        logging.getLogger(__name__).info("Local %s lane ready", args.lane)
        try:
            while not stop.is_set():
                if read_record("supervisor").get("stopping"):
                    break
                close_old_connections()
                try:
                    job = (tasks.tick, None) if args.lane == "scheduler" else next_job()
                    state["status"] = "ready"
                    if job:
                        task, identifier = job
                        state.update(
                            status="working",
                            task=task.name,
                            task_started_at=datetime.now(dt_timezone.utc).isoformat(),
                        )
                        try:
                            task.run(
                                *([str(identifier)] if identifier is not None else [])
                            )
                        finally:
                            state.update(
                                status="ready", task=None, task_started_at=None
                            )
                    stop.wait(15 if args.lane == "scheduler" else 0.8)
                except Exception:
                    # Record types/states are visible in Activity; never print
                    # provider bodies or raw task arguments into launcher logs.
                    logging.getLogger(__name__).warning(
                        "Local %s lane could not complete a poll; saved work remains available",
                        args.lane,
                    )
                    state["status"] = "recovering"
                    stop.wait(3)
        finally:
            write_record(args.lane, {**state, "status": "stopped"})
            close_old_connections()


if __name__ == "__main__":
    main()
