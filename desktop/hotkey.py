"""A narrow Windows hotkey, without global keyboard hooks or key logging."""

import ctypes
from ctypes import wintypes
import os
import threading


class VoiceHotkey:
    def __init__(self, callback):
        self.callback = callback
        self.registered = False
        self.thread_id = None
        self.ready = threading.Event()

    def start(self):
        if os.name != "nt":
            return
        threading.Thread(target=self.run, daemon=True).start()
        self.ready.wait(2)

    def run(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.registered = bool(
            user32.RegisterHotKey(None, 431, 0x0001 | 0x0002 | 0x4000, 0x20)
        )  # Alt+Ctrl+NoRepeat, Space.
        self.ready.set()
        if not self.registered:
            return
        try:
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == 431:
                    self.callback()
        finally:
            user32.UnregisterHotKey(None, 431)
            self.registered = False

    def close(self):
        if os.name == "nt" and self.thread_id and self.registered:
            ctypes.windll.user32.PostThreadMessageW(
                self.thread_id, 0x0012, 0, 0
            )  # WM_QUIT.


def focus_process_window(process):
    if os.name != "nt":
        return False
    import psutil

    try:
        parent = psutil.Process(process.pid)
        identifiers = {
            parent.pid,
            *(child.pid for child in parent.children(recursive=True)),
        }
    except psutil.Error:
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found = [False]

    def visit(window, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if pid.value in identifiers and user32.IsWindowVisible(window):
            user32.ShowWindow(window, 9)
            user32.SetForegroundWindow(window)
            found[0] = True
            return False
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(callback_type(visit), 0)
    return found[0]
