"""Durable local checkpoints guard against repeating external side effects."""

import hashlib
import json
import os
import sqlite3

from .policy import AttentionRequired, PolicyError


def fingerprint(job):
    args = {k: v for k, v in job["args"].items() if k != "resume_index"}
    raw = json.dumps({"tool": job["tool"], "args": args, "policy": job["policy"]}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Journal:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, next_action INTEGER NOT NULL DEFAULT 0, pending INTEGER NOT NULL DEFAULT 0, outcome TEXT)")
        self.connection.commit()
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def prepare(self, job):
        key, digest = str(job["id"]), fingerprint(job)
        row = self.connection.execute("SELECT fingerprint, next_action, pending, outcome FROM jobs WHERE id=?", (key,)).fetchone()
        if row is None:
            if job["args"].get("resume_index", 0) != 0:
                raise AttentionRequired("The local checkpoint is missing. Review prior actions before resolving this job.")
            self.connection.execute("INSERT INTO jobs(id, fingerprint) VALUES (?, ?)", (key, digest))
            self.connection.commit()
            return 0, None
        if row[0] != digest:
            raise PolicyError("A job's reviewed arguments or policy changed. Create a new reviewed job.")
        if row[2]:
            raise AttentionRequired("A previous mutation may have completed before the worker stopped. Inspect the result, then use companion resolve; it will not run again automatically.")
        outcome = json.loads(row[3]) if row[3] else None
        return row[1], outcome

    def pending(self, job_id, index):
        self.connection.execute("UPDATE jobs SET pending=1, next_action=?, outcome=NULL WHERE id=?", (index, str(job_id)))
        self.connection.commit()

    def checkpoint(self, job_id, index):
        self.connection.execute("UPDATE jobs SET pending=0, next_action=?, outcome=NULL WHERE id=?", (index, str(job_id)))
        self.connection.commit()

    def state(self, job_id):
        row = self.connection.execute("SELECT next_action,pending FROM jobs WHERE id=?", (str(job_id),)).fetchone()
        return (row[0], bool(row[1])) if row else (0, False)

    def finish(self, job_id, outcome, *, clear_pending=True):
        self.connection.execute("UPDATE jobs SET outcome=?, pending=CASE WHEN ? THEN 0 ELSE pending END WHERE id=?", (json.dumps(outcome), clear_pending, str(job_id)))
        self.connection.commit()

    def resolve(self, job_id, next_action):
        if not isinstance(next_action, int) or next_action < 0:
            raise ValueError("next_action must be a nonnegative index.")
        if not self.connection.execute("SELECT 1 FROM jobs WHERE id=?", (str(job_id),)).fetchone():
            raise ValueError("The job is not in this companion's journal.")
        self.checkpoint(job_id, next_action)

    def close(self):
        self.connection.close()


class WorkerLock:
    def __init__(self, state_dir):
        self.state_dir = state_dir
        self.file = None

    def __enter__(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.file = (self.state_dir / "worker.lock").open("a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError("Another companion process is using this state directory.") from exc
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.close()
