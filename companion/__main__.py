import argparse
import logging
from .config import Config

def main():
    parser = argparse.ArgumentParser(description="Derek Windows companion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Poll paired desktop jobs")
    login = sub.add_parser("login", help="Sign into the dedicated browser manually")
    login.add_argument("url")
    sub.add_parser("voice", help="Push-to-talk conversation")
    resolve = sub.add_parser("resolve", help="Record a checkpoint after manually inspecting an uncertain action")
    resolve.add_argument("job_id")
    resolve.add_argument("next_action", type=int)
    args = parser.parse_args()
    config = Config.from_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "run":
        from .client import APIClient
        from .runner import Worker
        Worker(config, APIClient(config)).run()
    elif args.command == "login":
        from .browser import manual_login
        from .journal import WorkerLock
        with WorkerLock(config.state_dir):
            manual_login(config.browser_profile, args.url)
    elif args.command == "voice":
        from .voice import voice_loop
        voice_loop(config)
    else:
        from .journal import Journal, WorkerLock
        with WorkerLock(config.state_dir):
            journal = Journal(config.state_dir / "jobs.sqlite3")
            try:
                journal.resolve(args.job_id, args.next_action)
            finally:
                journal.close()
        print("Local checkpoint recorded. This does not rerun or resume the server job. Inspect it in Activity; cancel it before starting a new reviewed run.")

if __name__ == "__main__":
    main()
