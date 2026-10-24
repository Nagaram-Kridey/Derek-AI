"""Start the installed portable router locally without passing Derek secrets."""

import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit


def ensure_router(env, root):
    if (env.get("MODEL_PROVIDER") != "freellmapi"
            or env.get("DEREK_FREELLMAPI_DESKTOP_AUTOSTART", "false").lower() != "true"):
        return
    url = urlsplit(env.get("FREELLMAPI_BASE_URL", ""))
    # Only this known local desktop installation is launched automatically.
    # External routers and custom URLs remain explicitly managed by the owner.
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.port != 31415:
        return
    try:
        with socket.create_connection(("127.0.0.1", 31415), timeout=1):
            return
    except OSError:
        pass
    executable = Path(root) / ".tools" / "freellmapi-0.16.5" / "FreeLLMAPI.exe"
    if not executable.is_file():
        raise RuntimeError("The configured FreeLLMAPI desktop installation is missing. Start your router or restore the installed portable app.")
    keep = {"PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "HOME", "APPDATA",
            "LOCALAPPDATA", "TEMP", "TMP", "PATHEXT", "COMSPEC"}
    subprocess.Popen([str(executable)], cwd=executable.parent,
                     env={key: value for key, value in env.items() if key.upper() in keep},
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    # The separately owned tray app remains running when Derek stops. Its own
    # single-instance handling prevents duplicates during concurrent startup.
