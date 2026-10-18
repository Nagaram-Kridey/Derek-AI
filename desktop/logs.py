"""Bounded child-process logs without blocking a service on disk failures."""

import logging
from logging.handlers import RotatingFileHandler
import threading


class QuietRotatingFileHandler(RotatingFileHandler):
    def handleError(self, record):
        # Logging failures must not dump the original record or credential
        # context to a different stream. Keep draining the child pipe instead.
        pass


class ServiceLog:
    def __init__(self, path):
        self.handler = QuietRotatingFileHandler(
            path, maxBytes=3_000_000, backupCount=1, encoding="utf-8", delay=True
        )
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.thread = None

    def capture(self, pipe):
        def consume():
            try:
                while chunk := pipe.read1(8192):
                    text = chunk.decode("utf-8", errors="replace").rstrip("\r\n")
                    self.handler.handle(
                        logging.LogRecord(
                            "derek.service", logging.INFO, "", 0, text, (), None
                        )
                    )
            except (OSError, ValueError):
                pass
            finally:
                pipe.close()
                self.handler.close()

        self.thread = threading.Thread(
            target=consume, name="derek-service-log", daemon=True
        )
        self.thread.start()

    def close(self):
        if self.thread:
            self.thread.join(timeout=2)
        else:
            self.handler.close()
