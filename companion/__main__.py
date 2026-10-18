import argparse
import logging
from dataclasses import replace
from .config import Config

def main():
    parser = argparse.ArgumentParser(description="Derek Windows companion")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Poll paired desktop jobs")
    login = sub.add_parser("login", help="Sign into the dedicated browser manually")
    login.add_argument("url")
    voice = sub.add_parser("voice", help="Start an explicitly armed voice session")
    voice.add_argument("--manual", action="store_true", help="Press Enter to end each utterance instead of silence detection")
    voice.add_argument("--barge-in", action="store_true", help="Allow spoken interruption during playback; requires headphones")
    sub.add_parser("audio-devices", help="List microphone/speaker choices without recording")
    private = sub.add_parser("private", help="Local Ollama chat with separate history and no cloud tools")
    private.add_argument("--voice", action="store_true", help="Local microphone recognition and installed Windows speech")
    private.add_argument("--speak", action="store_true", help="Speak typed-chat replies using an installed Windows voice")
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
        from .policy import AttentionRequired, PolicyError
        try:
            with WorkerLock(config.state_dir):
                manual_login(config.browser_profile, args.url, browser_channel=config.browser_channel)
        except (AttentionRequired, PolicyError, RuntimeError) as exc:
            parser.exit(1, f"Login setup: {exc}\n")
        except (EOFError, KeyboardInterrupt):
            print("\nLogin session ended. Close the dedicated browser windows before starting the worker.")
    elif args.command == "voice":
        from .voice import voice_loop
        if args.barge_in:
            config = replace(config, voice_barge_in=True)
        try:
            voice_loop(config, manual=args.manual)
        except RuntimeError as exc:
            parser.exit(1, f"Voice setup: {exc}\n")
    elif args.command == "private":
        from .private import private_loop
        try:
            private_loop(config, voice=args.voice, spoken=args.speak)
        except RuntimeError as exc:
            parser.exit(1, f"Private chat setup: {exc}\n")
    elif args.command == "audio-devices":
        import sounddevice as sd
        print(sd.query_devices())
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
