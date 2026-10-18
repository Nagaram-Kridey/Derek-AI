"""Automated tests must not call accounts, paid models, or local model servers."""

import socket
from urllib.parse import urlsplit
import os
import threading
import pytest


def pytest_sessionstart(session):
    if os.getenv("DJANGO_SETTINGS_MODULE") != "config.test_settings":
        pytest.exit(
            "Use config.test_settings for isolated tests; refusing an installation database or live account configuration.",
            returncode=2,
        )


@pytest.fixture(autouse=True)
def block_unmocked_network(monkeypatch, tmp_path):
    from django.core.cache import cache

    cache.clear()
    monkeypatch.setattr("desktop.credentials.read_owner_token", lambda _: None)
    monkeypatch.setattr("desktop.credentials.remember_owner_token", lambda *_: False)
    monkeypatch.setattr("desktop.credentials.forget_owner_token", lambda *_: None)
    monkeypatch.setenv("LILYLEO_STATE_DIR", str(tmp_path / "companion"))
    original = socket.socket.connect
    original_pair = socket.socketpair
    internal_pair = threading.local()
    database = urlsplit(os.getenv("DEREK_TEST_DATABASE_URL", ""))
    permitted_port = database.port or (
        5432 if database.scheme.startswith("postgres") else None
    )

    def connect(sock, address):
        if (
            getattr(internal_pair, "active", False)
            and isinstance(address, tuple)
            and address[0] in {"127.0.0.1", "::1"}
        ):
            return original(sock, address)
        if (
            isinstance(address, tuple)
            and permitted_port
            and address[1] == permitted_port
            and address[0] in {"127.0.0.1", "::1", "localhost"}
        ):
            return original(sock, address)
        raise AssertionError(
            "An automated check attempted an unmocked network connection."
        )

    def socketpair(*args, **kwargs):
        # Windows asyncio uses a private loopback socket pair for wakeups.
        # Permit only that constructor's thread, not application connections.
        internal_pair.active = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            internal_pair.active = False

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "socketpair", socketpair)
