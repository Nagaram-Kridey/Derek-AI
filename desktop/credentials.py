"""Windows-protected desktop session token, separate from provider API keys."""

import hashlib
import os
import re


def _name(api_url):
    return (
        "Derek.voice." + hashlib.sha256(api_url.rstrip("/").encode()).hexdigest()[:32]
    )


def read_owner_token(api_url):
    if os.name != "nt":
        return None
    try:
        import win32cred

        credential = win32cred.CredRead(_name(api_url), win32cred.CRED_TYPE_GENERIC)
        token = credential.get("CredentialBlob", b"")
        if isinstance(token, bytes):
            # pywin32 writes Unicode credential blobs as Windows UTF-16LE and
            # returns raw bytes. Retain the old ASCII representation if present.
            token = token.decode("utf-16-le" if len(token) == 80 else "utf-8")
        return (
            token
            if isinstance(token, str) and re.fullmatch(r"[0-9a-f]{40}", token)
            else None
        )
    except Exception:
        return None


def remember_owner_token(api_url, token, username):
    if (
        os.name != "nt"
        or not isinstance(token, str)
        or not re.fullmatch(r"[0-9a-f]{40}", token)
    ):
        return False
    try:
        import win32cred

        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": _name(api_url),
                "UserName": username,
                "CredentialBlob": token,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "Comment": "Derek desktop voice session for this Windows account",
            },
            0,
        )
        return True
    except Exception:
        return False


def forget_owner_token(api_url):
    if os.name != "nt":
        return
    try:
        import win32cred

        win32cred.CredDelete(_name(api_url), win32cred.CRED_TYPE_GENERIC, 0)
    except Exception:
        pass
