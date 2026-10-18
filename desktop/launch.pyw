"""Absolute-path entry point for a Windows shortcut and opt-in logon startup."""
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.chdir(root)

from desktop.__main__ import main

main()
