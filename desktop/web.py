"""The built local dashboard and API on one loopback-only origin."""

import os
import sys
from .state import ROOT

sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


if __name__ == "__main__":
    from config.wsgi import application
    from waitress import serve

    serve(
        application,
        host="127.0.0.1",
        port=8000,
        threads=6,
        ident="Derek",
        expose_tracebacks=False,
        max_request_body_size=22 * 1024 * 1024,
        channel_timeout=120,
    )
