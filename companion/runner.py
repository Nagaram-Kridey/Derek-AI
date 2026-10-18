"""Single-job worker. Completion can be retried without repeating a local task."""

import logging
import os
import threading
from pathlib import Path
import time

from .browser import run_browser
from .client import ClientError
from .files import execute_file
from .journal import Journal, WorkerLock
from .policy import ApprovalRequired, AttentionRequired, PathPolicy, PolicyError

log = logging.getLogger(__name__)
FILE_TOOLS = {"file.list", "file.read", "file.write", "file.move", "file.delete"}


class Worker:
    def __init__(self, config, client, journal=None, browser_executor=run_browser):
        self.config, self.client = config, client
        self.journal = journal or Journal(config.state_dir / "jobs.sqlite3")
        self.browser_executor = browser_executor

    def execute(self, job):
        observations = []
        job_id = job.get("id", "")
        try:
            if not job_id or not isinstance(job.get("args"), dict) or not isinstance(job.get("policy"), dict):
                raise PolicyError("Invalid desktop job.")
            start, previous = self.journal.prepare(job)
            if previous and previous["status"] in {"completed", "failed"}:
                return previous
            if previous:
                observations = previous.get("result", {}).get("observations", [])
            resume = job["args"].get("resume_index", 0)
            if not isinstance(resume, int) or resume > start:
                raise AttentionRequired("The server checkpoint is ahead of the local journal; inspect the job before resuming.")
            # A grant is bound to the checkpoint where it was reviewed. Once the
            # worker advances, a reconnect cannot authorize another risky step.
            approved = job.get("approved_risk") if resume == start else None
            if job["tool"] in FILE_TOOLS:
                from .desktop_state import desktop_unlocked
                if not desktop_unlocked():
                    raise AttentionRequired("Windows locked before the file action. Unlock and review before resuming.")
                remote = self.client.heartbeat()
                if remote.get("paused") or job_id in remote.get("stop_job_ids", []):
                    raise AttentionRequired("Automation was paused or cancelled before the file action.")
                if start:
                    raise AttentionRequired("The completed file operation needs its original result; it cannot be repeated.")
                workspace_profile = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "Derek"
                policy = PathPolicy(job["policy"].get("allowed_paths", []), [self.config.state_dir, workspace_profile, Path(__file__).resolve().parent.parent])
                mutation = job["tool"] not in {"file.read", "file.list"}
                if job["tool"] == "file.delete" and approved != "permanent_delete":
                    raise ApprovalRequired("permanent_delete")
                if mutation:
                    self.journal.pending(job_id, 0)
                result = execute_file(job["tool"], job["args"], policy, approved)
                # The result and completed marker share one SQLite transaction.
                outcome = {"status": "completed", "result": {**result, "next_action": 1}, "error": ""}
                self.journal.finish(job_id, outcome)
                return outcome
            if job["tool"] != "browser.run":
                raise PolicyError("Unknown desktop tool.")
            def check_interrupt():
                from .desktop_state import desktop_unlocked
                if not desktop_unlocked():
                    raise AttentionRequired("Windows locked. Browser interaction paused; inspect the last action before resuming.")
                status = self.client.heartbeat()
                if status.get("paused") or job_id in status.get("stop_job_ids", []):
                    raise AttentionRequired("Automation was paused or cancelled. Inspect the last action before resuming.")
            result = self.browser_executor(job["args"], job["policy"], self.config.browser_profile, browser_channel=getattr(self.config, "browser_channel", "chromium"), start=start, approved_risk=approved, before_mutation=lambda i: self.journal.pending(job_id, i), checkpoint=lambda i: self.journal.checkpoint(job_id, i), observations=observations, check_interrupt=check_interrupt)
            outcome = {"status": "completed", "result": result, "error": ""}
            self.journal.finish(job_id, outcome)
            return outcome
        except ApprovalRequired as exc:
            status, error, risk = "needs_approval", str(exc), exc.risk
        except AttentionRequired as exc:
            status, error, risk = "needs_attention", str(exc), None
        except (PolicyError, KeyError, UnicodeDecodeError, TypeError, ValueError) as exc:
            status, error, risk = "failed", str(exc), None
        except Exception:
            # Exception messages from Playwright/OS may contain user data.
            status, error, risk = "needs_attention", "The local operation failed or its result is uncertain. Inspect the desktop before retrying.", None
        next_action, pending = self.journal.state(job_id)
        outcome = {"status": status, "result": {"next_action": next_action, "observations": observations}, "error": error}
        if risk:
            outcome["risk"] = risk
        self.journal.finish(job_id, outcome, clear_pending=not pending or status in {"needs_approval", "failed"})
        return outcome

    def once(self):
        self.client.heartbeat()
        job = self.client.claim()
        if job is None:
            return False
        outcome = self.execute(job)
        self.client.complete(job, outcome)
        log.info("Desktop job %s: %s", job.get("id"), outcome["status"])
        return True

    def run(self):
        failures = 0
        stopped = threading.Event()
        runtime_state = {"status": "ready", "pid": os.getpid(), "mode": "local", "task": None}
        managed = os.getenv("DEREK_MANAGED_RUNTIME") == "true"
        if managed:
            from desktop.state import read_record, write_record
            def heartbeat():
                while not stopped.is_set():
                    try:
                        write_record("companion", dict(runtime_state))
                    except OSError:
                        pass
                    stopped.wait(5)
            threading.Thread(target=heartbeat, daemon=True).start()
        with WorkerLock(self.config.state_dir):
            try:
                while True:
                    if managed and read_record("supervisor").get("stopping"):
                        break
                    try:
                        from .desktop_state import desktop_unlocked
                        if not desktop_unlocked():
                            runtime_state["status"] = "locked"
                            time.sleep(self.config.poll_seconds)
                            continue
                        runtime_state["status"] = "working"
                        worked = self.once()
                        runtime_state["status"] = "ready"
                        failures = 0
                        if not worked:
                            time.sleep(self.config.poll_seconds)
                    except ClientError as exc:
                        runtime_state["status"] = "recovering"
                        failures += 1
                        log.warning("%s Reconnecting; local checkpoints are preserved.", exc)
                        time.sleep(min(60, self.config.poll_seconds * 2 ** min(failures, 4)))
            finally:
                stopped.set()
                if managed:
                    write_record("companion", {**runtime_state, "status": "stopped"})
                self.journal.close()
