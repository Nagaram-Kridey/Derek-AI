"""Own only fixed Derek processes, restart crashed services, drain on exit."""

from contextlib import suppress
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
import webbrowser

from .state import ROOT, RUNTIME, write_record

log = logging.getLogger("derek.desktop")
URL = "http://127.0.0.1:8000"
CONTROL_PORT = 8766


def child_environment():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "backend"), str(ROOT))),
        "DEREK_LOCAL_EXECUTION": "true",
        "DEREK_MANAGED_RUNTIME": "true",
        "LILYLEO_API_URL": "http://127.0.0.1:8000",
        "LILYLEO_ALLOW_LOCAL_HTTP": "true",
        "DJANGO_DEBUG": "false",
        "DJANGO_SECURE_SSL_REDIRECT": "false",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "PYTHONUNBUFFERED": "1",
    }


def python_path():
    path = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(path if path.exists() else Path(sys.executable).with_name("python.exe"))


class Supervisor:
    def __init__(self, open_page=True):
        self.env = child_environment()
        self.processes = {}
        self.failures = {}
        self.retry_at = {}
        self.started = datetime.now(timezone.utc).isoformat()
        self.stopping = False
        self.restarting = False
        self.open_page = open_page
        self.opened = False
        self.problem = None
        self.icon = None
        self.hotkey = None
        self.voice_process = None
        self.voice_private = False
        self.workspace_process = None
        self.backup_process = None
        self.next_backup_at = time.monotonic() + 60
        self.guard = threading.RLock()
        self.stop = threading.Event()
        self.logs = {}
        self.executables = {}
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.process_group = None
        self.services = {
            "backend": ["-m", "desktop.web"],
            **{
                lane: ["-m", "assistant.local_worker", lane]
                for lane in ("interactive", "research", "delivery", "scheduler")
            },
        }
        if self.env.get("LILYLEO_DEVICE_TOKEN"):
            self.services["companion"] = ["-m", "companion", "run"]
        if (
            self.env.get("TELEGRAM_BOT_TOKEN")
            and self.env.get("TELEGRAM_CHAT_ID")
            and self.env.get("DEREK_TELEGRAM_POLLING", "true").lower() == "true"
        ):
            self.services["telegram"] = ["-m", "desktop.telegram"]
        ollama = Path(self.env.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
        executable = str(ollama) if ollama.is_file() else shutil.which("ollama")
        if executable and (
            self.env.get("MODEL_PROVIDER") == "ollama" or self.env.get("OLLAMA_MODEL")
        ):
            self.services["ollama"] = ["serve"]
            self.executables["ollama"] = executable

    def prepare(self):
        if not (ROOT / "backend/staticapp/index.html").exists():
            raise RuntimeError(
                "Build the dashboard first with scripts/build-local.ps1. The local app needs no Node server after that."
            )
        # Refuse an overlapping development/Celery installation. Never kill an
        # unowned process or silently enable two authoritative schedulers.
        import psutil

        current = psutil.Process()
        relatives = {current.pid, *(p.pid for p in current.parents())}
        for process in psutil.process_iter(["pid", "exe", "cmdline", "cwd"]):
            with suppress(psutil.Error, OSError):
                info = process.info
                if (
                    info["pid"] in relatives
                    or not info["cwd"]
                    or Path(info["cwd"]).resolve() != ROOT
                ):
                    continue
                args = info["cmdline"] or []
                if "celery" in args or any("runserver" == arg for arg in args):
                    raise RuntimeError(
                        "A development server or Celery worker is still running for this project. Stop that runtime before starting Derek locally."
                    )
        import socket

        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", 8000))
            except OSError:
                raise RuntimeError(
                    "Port 8000 is already in use. Stop that service before starting the local app."
                ) from None
        # Backups and migrations happen before workers can accept any jobs.
        result = subprocess.run(
            [python_path(), "-m", "desktop.prepare"],
            cwd=ROOT,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            raise RuntimeError(
                "Database preparation failed. Review the existing environment and migrations before starting services."
            )

    def launch(self, name):
        if name not in self.services or self.stopping:
            return
        log_path = RUNTIME / (name + ".log")
        from .logs import ServiceLog

        stream = ServiceLog(log_path)
        self.logs[name] = stream
        env = self.env
        if name == "ollama":
            # The local model server needs no Derek account/API credentials or
            # proxy settings. Keep them out of its process and startup logs.
            keep = {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "USERPROFILE",
                "HOME",
                "APPDATA",
                "LOCALAPPDATA",
                "TEMP",
                "TMP",
                "PATHEXT",
                "COMSPEC",
                "OLLAMA_MODELS",
            }
            env = {key: value for key, value in self.env.items() if key.upper() in keep}
            env.update(
                OLLAMA_HOST="127.0.0.1:11434",
                OLLAMA_NO_CLOUD="1",
                OLLAMA_NUM_PARALLEL="1",
            )
        process = subprocess.Popen(
            [self.executables.get(name, python_path()), *self.services[name]],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                | (
                    subprocess.BELOW_NORMAL_PRIORITY_CLASS
                    if name in {"ollama", "research"}
                    else 0
                )
            )
            if os.name == "nt"
            else 0,
        )
        stream.capture(process.stdout)
        self.processes[name] = process
        if self.process_group:
            self.process_group.add(process)
        write_record(name, {"status": "starting", "pid": process.pid, "mode": "local"})
        log.info("Started local service %s", name)

    def status(self):
        with self.guard:
            return {
                "mode": "local",
                "pid": os.getpid(),
                "started_at": self.started,
                "status": "stopping"
                if self.stopping
                else "needs_attention"
                if self.problem
                else "running",
                "problem": self.problem,
                "url": URL,
                "stopping": self.stopping,
                "voice_shortcut": "Ctrl+Alt+Space"
                if self.hotkey and self.hotkey.registered
                else None,
                "start_at_login": self.autostart_enabled(),
                "services": {
                    name: {
                        "alive": process.poll() is None,
                        "restarts": self.failures.get(name, 0),
                    }
                    for name, process in self.processes.items()
                },
            }

    def request_stop(self, restart=False):
        with self.guard:
            self.stopping, self.restarting = True, restart
            write_record("supervisor", self.status())
        log.info("Local runtime draining; restart=%s", restart)

    def open_workspace(self, *_):
        if os.name == "nt":
            from .hotkey import focus_process_window

            if (
                self.workspace_process
                and self.workspace_process.poll() is None
                and focus_process_window(self.workspace_process)
            ):
                return
            candidates = [
                Path(self.env.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
                / "Microsoft/Edge/Application/msedge.exe",
                Path(self.env.get("PROGRAMFILES", "C:/Program Files"))
                / "Microsoft/Edge/Application/msedge.exe",
                Path(self.env.get("PROGRAMFILES", "C:/Program Files"))
                / "Google/Chrome/Application/chrome.exe",
                Path(self.env.get("LOCALAPPDATA", ""))
                / "Google/Chrome/Application/chrome.exe",
            ]
            executable = next(
                (candidate for candidate in candidates if candidate.is_file()), None
            )
            if executable:
                # This profile is only for Derek's dashboard. It is distinct
                # from both the user's normal browser and automation sessions.
                profile = (
                    Path(self.env.get("LOCALAPPDATA", str(ROOT / ".companion")))
                    / "Derek"
                    / "workspace-profile"
                )
                profile.mkdir(parents=True, exist_ok=True)
                self.workspace_process = subprocess.Popen(
                    [
                        str(executable),
                        "--app=" + URL,
                        "--user-data-dir=" + str(profile),
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-mode",
                    ],
                    cwd=ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
        webbrowser.open(URL)

    def voice_console(self, private=False):
        # Explicit tray action opens an interactive console. Capture remains
        # closed until the user arms the voice session.
        args = [python_path(), "-m", "companion", "private" if private else "voice"]
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            env=self.env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        if self.process_group:
            self.process_group.add(process)

    def voice_window(self, private=False):
        if self.stopping or self.problem or self.process_group is None:
            return False
        with self.guard:
            if self.voice_process and self.voice_process.poll() is None:
                from .hotkey import focus_process_window

                focus_process_window(self.voice_process)
                if private != self.voice_private and self.icon:
                    self.icon.notify(
                        "Close the current voice window before changing between online and private mode.",
                        "Choose your voice mode",
                    )
                return private == self.voice_private
            executable = (
                str(Path(python_path()).with_name("pythonw.exe"))
                if os.name == "nt"
                else python_path()
            )
            self.voice_process = subprocess.Popen(
                [
                    executable,
                    "-m",
                    "desktop.voice_window",
                    *(["--private"] if private else []),
                ],
                cwd=ROOT,
                env=self.env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.voice_private = private
            if self.process_group:
                self.process_group.add(self.voice_process)
            return True

    def voice_shortcut(self):
        self.voice_window(
            private=self.voice_private
            if self.voice_process and self.voice_process.poll() is None
            else False
        )

    def open_logs(self, *_):
        if os.name == "nt":
            os.startfile(RUNTIME)

    def autostart(self, enable):
        if os.name != "nt":
            return
        import winreg

        # The setting is opt-in; installation never enables it silently.
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        ) as key:
            if enable:
                executable = str(Path(python_path()).with_name("pythonw.exe"))
                entry = subprocess.list2cmdline(
                    [executable, str(ROOT / "desktop/launch.pyw"), "--no-open"]
                )
                winreg.SetValueEx(key, "DerekLocal", 0, winreg.REG_SZ, entry)
            else:
                with suppress(FileNotFoundError):
                    winreg.DeleteValue(key, "DerekLocal")

    @staticmethod
    def autostart_enabled():
        if os.name != "nt":
            return False
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
            ) as key:
                winreg.QueryValueEx(key, "DerekLocal")
            return True
        except OSError:
            return False

    def control_server(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                # No CORS; browsers cannot invoke local controls. A random token
                # is read only by this project's CLI from its private runtime file.
                if (
                    self.headers.get("Origin")
                    or self.headers.get("Host") != f"127.0.0.1:{CONTROL_PORT}"
                    or not secrets.compare_digest(
                        self.headers.get("Authorization", ""), "Bearer " + owner.token
                    )
                ):
                    self.send_error(403)
                    return
                if self.path not in {
                    "/open",
                    "/stop",
                    "/restart",
                    "/voice",
                    "/private-voice",
                    "/autostart-on",
                    "/autostart-off",
                }:
                    self.send_error(404)
                    return
                if self.path == "/open":
                    owner.open_workspace()
                elif self.path in {"/voice", "/private-voice"}:
                    if not owner.voice_window(private=self.path == "/private-voice"):
                        self.send_error(409)
                        return
                elif self.path in {"/autostart-on", "/autostart-off"}:
                    owner.autostart(self.path == "/autostart-on")
                    write_record("supervisor", owner.status())
                else:
                    owner.request_stop(restart=self.path == "/restart")
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        credential = RUNTIME / "control.json"
        descriptor = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"token": self.token, "pid": os.getpid()}, stream)

    def backend_ready(self):
        try:
            with urlopen(URL + "/health/", timeout=1) as response:
                return response.status == 200
        except (OSError, ValueError):
            return False

    def watch(self):
        try:
            # Keep stop/restart available even if a database/dependency check
            # fails. Preparation completes before any service can claim work.
            self.control_server()
            self.prepare()
            if self.stopping:
                return
            from .process_group import ProcessGroup

            self.process_group = ProcessGroup()
            from .hotkey import VoiceHotkey

            self.hotkey = VoiceHotkey(self.voice_shortcut)
            self.hotkey.start()
            write_record("supervisor", self.status())
            if "ollama" in self.services:
                try:
                    with urlopen(
                        "http://127.0.0.1:11434/api/version", timeout=1
                    ) as response:
                        if response.status == 200:
                            del self.services[
                                "ollama"
                            ]  # An existing model service is not ours to stop.
                except (OSError, ValueError):
                    pass
            for name in sorted(self.services, key=lambda name: name != "ollama"):
                self.launch(name)
            while not self.stop.wait(2):
                with self.guard:
                    write_record("supervisor", self.status())
                    if self.stopping:
                        lanes = [
                            name
                            for name in self.services
                            if name not in {"backend", "ollama"}
                        ]
                        voice_finished = (
                            self.voice_process is None
                            or self.voice_process.poll() is not None
                        )
                        backup_finished = (
                            self.backup_process is None
                            or self.backup_process.poll() is not None
                        )
                        if (
                            all(
                                self.processes[name].poll() is not None
                                for name in lanes
                            )
                            and voice_finished
                            and backup_finished
                        ):
                            break
                    else:
                        for name, process in list(self.processes.items()):
                            if process.poll() is None:
                                if name == "backend":
                                    write_record(
                                        name,
                                        {
                                            "status": "ready"
                                            if self.backend_ready()
                                            else "starting",
                                            "pid": process.pid,
                                            "mode": "local",
                                        },
                                    )
                                elif name == "ollama":
                                    write_record(
                                        name,
                                        {
                                            "status": "ready",
                                            "pid": process.pid,
                                            "mode": "local",
                                        },
                                    )
                                continue
                            self.logs[name].close()
                            if name not in self.retry_at:
                                self.failures[name] = self.failures.get(name, 0) + 1
                                self.retry_at[name] = time.monotonic() + min(
                                    60, 2 ** min(self.failures[name], 6)
                                )
                                write_record(
                                    name,
                                    {
                                        "status": "recovering",
                                        "mode": "local",
                                        "restarts": self.failures[name],
                                    },
                                )
                                log.warning(
                                    "Local service %s exited; restart scheduled", name
                                )
                            if time.monotonic() >= self.retry_at[name]:
                                del self.retry_at[name]
                                self.launch(name)
                if not self.opened and self.open_page and self.backend_ready():
                    self.open_workspace()
                    self.opened = True
                if (
                    not self.stopping
                    and time.monotonic() >= self.next_backup_at
                    and (
                        self.backup_process is None
                        or self.backup_process.poll() is not None
                    )
                ):
                    self.backup_process = subprocess.Popen(
                        [python_path(), "-m", "desktop.backup"],
                        cwd=ROOT,
                        env=self.env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=(
                            subprocess.CREATE_NO_WINDOW
                            | subprocess.BELOW_NORMAL_PRIORITY_CLASS
                        )
                        if os.name == "nt"
                        else 0,
                    )
                    self.next_backup_at = time.monotonic() + 24 * 60 * 60
                    if self.process_group:
                        self.process_group.add(self.backup_process)
                if self.icon:
                    self.icon.title = "Derek · " + (
                        "Finishing current work" if self.stopping else "Running locally"
                    )
        except Exception as exc:
            self.problem = (
                str(exc)
                if isinstance(exc, RuntimeError)
                else "Local startup needs attention. Check the runtime setup guide."
            )
            write_record("supervisor", self.status())
            log.error("%s", self.problem)
            if self.icon:
                with suppress(Exception):
                    self.icon.notify(self.problem, "Derek needs attention")
                self.icon.title = "Derek · Setup needs attention"
            # Keep the tray available for logs/exit even after startup fails.
            while self.icon and not self.stopping and not self.stop.wait(2):
                write_record("supervisor", self.status())
        finally:
            self.stop.set()
            self.cleanup()
            if self.icon:
                self.icon.stop()

    def cleanup(self):
        import psutil

        if self.hotkey:
            self.hotkey.close()
        owned = []
        for name, process in self.processes.items():
            if process.poll() is None:
                with suppress(psutil.Error):
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        with suppress(psutil.Error):
                            child.terminate()
                            owned.append(child)
                    parent.terminate()
                    owned.append(parent)
            write_record(name, {"status": "stopped", "mode": "local"})
        # Wait for this supervisor's processes to release ports and file locks
        # before a restart. Never terminate an independently running service.
        _, alive = psutil.wait_procs(owned, timeout=5)
        for process in alive:
            with suppress(psutil.Error):
                process.kill()
        psutil.wait_procs(alive, timeout=5)
        if self.process_group:
            self.process_group.close()
        for stream in self.logs.values():
            stream.close()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        with suppress(OSError):
            (RUNTIME / "control.json").unlink()
        write_record("supervisor", {"status": "stopped", "stopping": True})
        if self.restarting:
            executable = (
                str(Path(python_path()).with_name("pythonw.exe"))
                if os.name == "nt"
                else python_path()
            )
            # The lock is released when this process exits; new launcher waits.
            subprocess.Popen(
                [executable, str(ROOT / "desktop/launch.pyw"), "--no-open", "--wait"],
                cwd=ROOT,
                env=self.env,
            )

    def run(self, tray=True):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            RUNTIME / "launcher.log",
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.setLevel(logging.INFO)
        log.addHandler(handler)
        if tray:
            import pystray
            from PIL import Image, ImageDraw

            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((2, 2, 62, 62), radius=17, fill="#183b36")
            draw.polygon(
                (
                    (32, 11),
                    (38, 26),
                    (53, 32),
                    (38, 38),
                    (32, 53),
                    (26, 38),
                    (11, 32),
                    (26, 26),
                ),
                fill="#d3eadc",
            )
            menu = pystray.Menu(
                pystray.MenuItem("Open Derek", self.open_workspace, default=True),
                pystray.MenuItem(
                    "Open voice window · Ctrl+Alt+Space", lambda *_: self.voice_window()
                ),
                pystray.MenuItem(
                    "Private local voice", lambda *_: self.voice_window(private=True)
                ),
                pystray.MenuItem(
                    "Private local chat", lambda *_: self.voice_console(private=True)
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Start at Windows sign-in",
                    lambda item, _: self.autostart(not self.autostart_enabled()),
                    checked=lambda _: self.autostart_enabled(),
                ),
                pystray.MenuItem("Open local logs", self.open_logs),
                pystray.MenuItem(
                    "Restart after current work",
                    lambda *_: self.request_stop(restart=True),
                ),
                pystray.MenuItem(
                    "Quit after current work", lambda *_: self.request_stop()
                ),
            )
            self.icon = pystray.Icon("Derek", image, "Derek · Starting", menu)
            self.icon.run(
                setup=lambda icon: (setattr(icon, "visible", True), self.watch())
            )
        else:
            signal.signal(signal.SIGINT, lambda *_: self.request_stop())
            self.watch()


def send_control(action):
    try:
        credential = json.loads((RUNTIME / "control.json").read_text(encoding="utf-8"))
        request = Request(
            f"http://127.0.0.1:{CONTROL_PORT}/{action}",
            data=b"",
            method="POST",
            headers={"Authorization": "Bearer " + credential["token"]},
        )
        with urlopen(request, timeout=3) as response:
            return response.status == 204
    except (OSError, ValueError, KeyError):
        return False
