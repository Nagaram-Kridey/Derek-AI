import argparse
import json
import time

from companion.journal import WorkerLock
from .state import RUNTIME, snapshot


def main():
    parser = argparse.ArgumentParser(description="Derek local app")
    parser.add_argument(
        "command",
        choices=("run", "status", "open", "stop", "restart"),
        default="run",
        nargs="?",
    )
    parser.add_argument("--no-tray", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    from .supervisor import Supervisor, send_control

    if args.command == "status":
        print(json.dumps(snapshot(), indent=2))
    elif args.command != "run":
        if not send_control(args.command):
            parser.exit(
                1,
                "Derek is not running, or its local control connection is unavailable.\n",
            )
    else:
        deadline = time.monotonic() + (45 if args.wait else 0)
        while True:
            lock = WorkerLock(RUNTIME / "launcher-lock")
            try:
                lock.__enter__()
                break
            except RuntimeError:
                if time.monotonic() < deadline:
                    time.sleep(1)
                    continue
                if not args.no_open:
                    send_control("open")
                return
        try:
            Supervisor(open_page=not args.no_open).run(tray=not args.no_tray)
        finally:
            lock.__exit__()


if __name__ == "__main__":
    main()
