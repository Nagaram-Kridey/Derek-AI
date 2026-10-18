"""Current-user shortcut and optional sign-in startup; no admin access."""

import argparse
import os
from pathlib import Path
import subprocess

from .state import ROOT, RUNTIME
from .supervisor import Supervisor, python_path


def main():
    parser = argparse.ArgumentParser(description="Install a local Derek shortcut")
    parser.add_argument(
        "--autostart", action="store_true", help="Start the tray app at Windows sign-in"
    )
    args = parser.parse_args()
    if os.name != "nt":
        parser.exit(1, "The local shortcut installer is for Windows.\n")
    import win32com.client
    from PIL import Image, ImageDraw

    RUNTIME.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=65, fill="#183b36")
    draw.polygon(
        (
            (128, 44),
            (152, 104),
            (212, 128),
            (152, 152),
            (128, 212),
            (104, 152),
            (44, 128),
            (104, 104),
        ),
        fill="#d3eadc",
    )
    icon = RUNTIME / "derek.ico"
    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SpecialFolders("Desktop"))
    shortcut_path = desktop / "Derek.lnk"
    executable = str(Path(python_path()).with_name("pythonw.exe"))
    arguments = subprocess.list2cmdline([str(ROOT / "desktop/launch.pyw")])
    if shortcut_path.exists():
        existing = shell.CreateShortcut(str(shortcut_path))
        if (
            existing.TargetPath.lower() != executable.lower()
            or existing.Arguments != arguments
        ):
            shortcut_path = desktop / "Derek Local.lnk"
            if shortcut_path.exists():
                parser.exit(
                    1,
                    "A different Derek shortcut exists. Keep it and create this project's shortcut manually.\n",
                )
    shortcut = shell.CreateShortcut(str(shortcut_path))
    shortcut.TargetPath = executable
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = str(ROOT)
    shortcut.IconLocation = str(icon)
    shortcut.Description = "Derek · Your local personal assistant"
    shortcut.Save()
    if args.autostart:
        Supervisor().autostart(True)
    print("Local shortcut created:", shortcut_path.name)
    print(
        "Windows sign-in startup:",
        "enabled" if Supervisor.autostart_enabled() else "off",
    )


if __name__ == "__main__":
    main()
