"""Checks shared by typed tools. Model output never overrides this policy."""

import ipaddress
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit


class PolicyError(ValueError):
    pass


class AttentionRequired(Exception):
    pass


class ApprovalRequired(Exception):
    def __init__(self, risk):
        self.risk = risk
        super().__init__(f"Approval required for {risk}.")


RISKS = {"purchase", "payment", "account_security", "permanent_delete"}


def normalized_host(host):
    if not isinstance(host, str) or not host or any(c in host for c in "/:@?#\\*"):
        raise PolicyError("Allowed domains must be exact hostnames without wildcards or ports.")
    try:
        host = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise PolicyError("Invalid domain.") from exc
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        raise PolicyError("Invalid domain.")
    return host


class DomainPolicy:
    def __init__(self, domains, resolver=socket.getaddrinfo):
        if not isinstance(domains, list):
            raise PolicyError("allowed_domains must be a list.")
        self.domains = {normalized_host(d) for d in domains}
        self.resolver = resolver

    def check(self, url):
        try:
            parsed = urlsplit(url)
            host = normalized_host(parsed.hostname or "")
            port = parsed.port
        except (ValueError, TypeError) as exc:
            raise PolicyError("Invalid browser URL.") from exc
        if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443) or host not in self.domains:
            raise PolicyError("Browser URL is outside the approved HTTPS domains.")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise PolicyError("Private network domains are unavailable to browser workflows.")
        try:
            addresses = {entry[4][0] for entry in self.resolver(host, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise PolicyError("Browser domain could not be resolved.") from exc
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise PolicyError("Browser domains must resolve exclusively to public IP addresses.")
        return url


class PathPolicy:
    def __init__(self, allowed_paths, protected_paths=()):
        if not isinstance(allowed_paths, list):
            raise PolicyError("allowed_paths must be a list.")
        self.roots = []
        for value in allowed_paths:
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise PolicyError("Approved folders must be absolute paths.")
            root = path.resolve(strict=True)
            if not root.is_dir() or root == Path(root.anchor):
                raise PolicyError("Approve a specific existing folder, not a filesystem root.")
            self.roots.append(root)
        self.protected = [Path(p).resolve() for p in protected_paths]

    def check(self, value, *, allow_root=False):
        if not isinstance(value, str) or not value or "\x00" in value:
            raise PolicyError("A valid absolute path is required.")
        path = Path(value).expanduser()
        if not path.is_absolute() or ".." in path.parts:
            raise PolicyError("Relative paths and parent traversal are not permitted.")
        # Reject Windows alternate data streams, UNC/device paths, and reserved names
        # even when tests run on another platform.
        if value.startswith(("\\\\", "//")) or any(":" in p for p in path.parts[1:]):
            raise PolicyError("Network paths and alternate data streams are not permitted.")
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        if any(part.rstrip(" .").split(".")[0].upper() in reserved or part.endswith((" ", ".")) for part in path.parts[1:]):
            raise PolicyError("Reserved or ambiguous path names are not permitted.")
        resolved = path.resolve(strict=False)
        if any(resolved == p or resolved.is_relative_to(p) for p in self.protected):
            raise PolicyError("Companion state, credentials, and browser profiles cannot be accessed by tools.")
        if not any(resolved.is_relative_to(root) and (allow_root or resolved != root) for root in self.roots):
            raise PolicyError("Path is outside the approved folders or targets the approved folder itself.")
        return resolved


def detect_risk(text):
    value = text.lower()
    checks = (
        ("permanent_delete", r"\b(delete|erase|destroy|remove permanently|empty trash)\b"),
        ("account_security", r"\b(password|passkey|security|recovery|two.factor|2fa|mfa|authentication|api.key|access.token|sign.out|log.out)\b"),
        ("payment", r"\b(pay|payment|transfer|send money|billing|bank|credit.card|debit.card)\b"),
        ("purchase", r"\b(buy|purchase|checkout|place order|subscribe|confirm order)\b"),
    )
    for risk, pattern in checks:
        if re.search(pattern, value):
            return risk
    return None
