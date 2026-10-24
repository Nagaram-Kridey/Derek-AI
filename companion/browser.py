"""Visible Chromium automation using a dedicated local profile and typed actions."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess

from .policy import ApprovalRequired, AttentionRequired, DomainPolicy, PolicyError, RISKS, detect_risk

MUTATIONS = {"fill", "click", "select"}
ACTIONS = MUTATIONS | {"navigate", "read", "wait", "scroll"}
CHALLENGE = re.compile(r"verify (?:that )?you(?: are|'re) (?:a )?human|captcha|enter (?:the |your )?(?:verification|authentication|security) code|two.factor authentication|multi.factor authentication", re.I)


def check_page(page, domains):
    domains.check(page.url)
    text = page.locator("body").inner_text(timeout=10_000)[:100_000]
    if CHALLENGE.search(text):
        raise AttentionRequired("The site requires a CAPTCHA or account verification. Complete it manually in the local browser.")
    for selector in ('input[type="password"]', 'input[autocomplete="one-time-code"]', 'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]'):
        for element in page.locator(selector).all():
            if element.is_visible():
                raise AttentionRequired("Sign-in or account verification requires manual interaction.")
    return text


def target_risk(target, action):
    fields = [target.inner_text(timeout=5_000)[:2000]]
    for attr in ("aria-label", "title", "name", "id", "type", "href", "formaction", "autocomplete", "value"):
        fields.append(target.get_attribute(attr) or "")
    detected = detect_risk(" ".join(fields))
    declared = action.get("risk", "normal")
    if declared not in RISKS | {"normal"}:
        raise PolicyError("Unknown action risk.")
    return detected or (declared if declared != "normal" else None)


def resolve_target(page, action):
    """Exact semantic locators survive layout changes without guessing a target."""
    selector, target = action.get("selector"), action.get("target")
    if selector and target:
        raise PolicyError("Choose either selector or semantic target.")
    if target is None:
        if selector is None and action.get("type") == "read":
            selector = "body"
        if not isinstance(selector, str) or not selector.strip():
            raise PolicyError("A unique selector or semantic target is required.")
        return page.locator(selector)
    if not isinstance(target, dict) or set(target) - {"by", "value", "name"}:
        raise PolicyError("Invalid semantic target.")
    by, value, name = target.get("by"), target.get("value"), target.get("name")
    if not isinstance(value, str) or not 1 <= len(value) <= 500:
        raise PolicyError("Semantic targets need bounded nonempty text.")
    if by == "role":
        if not isinstance(name, str) or not 1 <= len(name) <= 500:
            raise PolicyError("Role targets require an exact accessible name.")
        return page.get_by_role(value, name=name, exact=True)
    if name is not None:
        raise PolicyError("Only role targets accept name.")
    methods = {"label": page.get_by_label, "text": page.get_by_text,
               "placeholder": page.get_by_placeholder, "test_id": page.get_by_test_id}
    if by not in methods:
        raise PolicyError("Unknown semantic locator type.")
    return methods[by](value, **({} if by == "test_id" else {"exact": True}))


def execute_actions(page, actions, domains, *, start=0, approved_risk=None, before_mutation=lambda i: None, checkpoint=lambda i: None, observations=None, check_interrupt=lambda: None):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
        raise PolicyError("Browser workflows need 1 to 30 typed actions.")
    if not 0 <= start <= len(actions):
        raise PolicyError("Invalid browser checkpoint.")
    observations = observations if observations is not None else []
    remaining_approval = approved_risk
    for index in range(start, len(actions)):
        action = actions[index]
        if not isinstance(action, dict) or action.get("type") not in ACTIONS:
            raise PolicyError("Unknown browser action; scripts and shell commands are unavailable.")
        kind = action["type"]
        check_interrupt()
        if kind == "navigate":
            domains.check(action.get("url", ""))
            page.goto(action["url"], wait_until="domcontentloaded", timeout=30_000)
            text = check_page(page, domains)
            if action.get("expected_text") and action["expected_text"] not in text:
                raise AttentionRequired("Navigation reached an unexpected page.")
        else:
            text = check_page(page, domains)
            target = resolve_target(page, action)
            if kind == "wait":
                timeout = action.get("timeout_ms", 10000)
                if type(timeout) is not int or not 100 <= timeout <= 30000:
                    raise PolicyError("Wait timeout must be 100 to 30000 milliseconds.")
                target.wait_for(state="visible", timeout=timeout)
                check_interrupt()
                text = check_page(page, domains)
            if kind in {"read", "wait", "scroll"}:
                if action.get("expected_url"):
                    domains.check(action["expected_url"])
                    if page.url != action["expected_url"]:
                        raise AttentionRequired("The page URL differs from the reviewed workflow.")
                if action.get("expected_text") and action["expected_text"] not in text:
                    raise AttentionRequired("The expected page text was not found.")
                if target.count() != 1 or not target.is_visible():
                    raise AttentionRequired("The target must identify exactly one visible element.")
            if kind == "read":
                observations.append({"action": index, "url": page.url, "text": target.inner_text(timeout=10_000)[:20_000]})
            elif kind == "scroll":
                target.scroll_into_view_if_needed(timeout=10_000)
                check_interrupt()
                check_page(page, domains)
            elif kind in MUTATIONS:
                expected_url, expected_text = action.get("expected_url"), action.get("expected_text")
                if not isinstance(expected_url, str) or not isinstance(expected_text, str) or not expected_text.strip():
                    raise PolicyError("Mutating actions require expected_url and nonempty expected_text.")
                domains.check(expected_url)
                if page.url != expected_url or expected_text not in text:
                    raise AttentionRequired("The current page differs from the reviewed workflow. No action was taken.")
                if target.count() != 1 or not target.is_visible() or not target.is_enabled():
                    raise AttentionRequired("The action target must be unique, visible, and enabled.")
                risk = target_risk(target, action)
                if risk and risk != remaining_approval:
                    raise ApprovalRequired(risk)
                if risk:
                    remaining_approval = None
                if kind in {"fill", "select"} and not isinstance(action.get("value"), str):
                    raise PolicyError("Fill and select require a string value.")
                before_mutation(index)
                if kind == "click":
                    target.click(timeout=15_000)
                elif kind == "fill":
                    target.fill(action["value"], timeout=15_000)
                else:
                    target.select_option(action["value"], timeout=15_000)
                # Persist immediately after the operation before inspecting a
                # resulting page; a later challenge must not repeat the click.
                checkpoint(index + 1)
                check_interrupt()
                check_page(page, domains)
        checkpoint(index + 1)
    return {"next_action": len(actions), "observations": observations, "url": page.url}


@contextmanager
def persistent_browser(profile, resolver_rules=None, *, browser_channel="chromium"):
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install companion browser dependencies and run: python -m playwright install chromium") from exc
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        args = ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]
        if resolver_rules:
            args.append("--host-resolver-rules=" + resolver_rules)
        options = {"channel": browser_channel} if browser_channel in {"chrome", "msedge"} else {}
        context = playwright.chromium.launch_persistent_context(str(profile), headless=False, service_workers="block", accept_downloads=False, args=args, **options)
        try:
            context.set_default_timeout(15_000)
            yield context
        finally:
            try:
                context.close()
            except PlaywrightError as exc:
                # A user may already have closed the persistent browser window.
                # Do not mask an earlier navigation error with cleanup failure.
                if type(exc).__name__ != "TargetClosedError":
                    raise


def run_browser(args, policy, profile, *, browser_channel="chromium", **callbacks):
    domains = DomainPolicy(policy.get("allowed_domains", []))
    import socket
    import ipaddress
    mappings = []
    for host in domains.domains:
        domains.check("https://" + host)
        address = sorted({record[4][0] for record in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})[0]
        if not ipaddress.ip_address(address).is_global:
            raise PolicyError("Browser hostname resolved to a private address")
        mappings.append(f"MAP {host} {address}")
    mappings.append("MAP * ~NOTFOUND")
    blocked = []
    external_interrupt = callbacks.pop("check_interrupt", lambda: None)
    with persistent_browser(profile, ", ".join(mappings), browser_channel=browser_channel) as context:
        def route_request(route):
            try:
                domains.check(route.request.url)
            except PolicyError:
                blocked.append("A browser request left the approved public domains.")
                route.abort()
            else:
                route.continue_()

        context.route("**/*", route_request)
        # WebSockets bypass normal route interception. This assistant's actions
        # do not need them; blocking prevents an unapproved secondary channel.
        context.route_web_socket("**/*", lambda ws: ws.close())
        page = context.pages[0] if context.pages else context.new_page()
        for extra in context.pages[1:]:
            extra.close()

        def popup(opened):
            blocked.append("The site opened a new tab; review it manually before continuing.")
            opened.close()

        context.on("page", popup)
        page.on("dialog", lambda dialog: (blocked.append("The page opened a confirmation dialog."), dialog.dismiss()))
        page.on("download", lambda download: (blocked.append("The page attempted a download."), download.cancel()))

        def check_interrupt():
            external_interrupt()
            if blocked:
                raise AttentionRequired(blocked[0])

        return execute_actions(page, args.get("actions"), domains, check_interrupt=check_interrupt, **callbacks)


def _installed_browser(channel):
    """Locate an installed vendor browser for a human-controlled login session."""
    vendor = {"chrome": ("Google", "Chrome", "Application", "chrome.exe"),
              "msedge": ("Microsoft", "Edge", "Application", "msedge.exe")}[channel]
    for root in (os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("LOCALAPPDATA")):
        if root:
            executable = Path(root).joinpath(*vendor)
            if executable.is_file():
                return str(executable)
    executable = shutil.which("google-chrome" if channel == "chrome" else "microsoft-edge")
    if executable:
        return executable
    raise RuntimeError("Install Google Chrome or Microsoft Edge for the selected browser channel.")


def manual_login(profile, url, *, browser_channel="chromium"):
    # Manual mode lets the user complete external identity-provider redirects.
    # It exposes no automation, credentials, or browser data to the server.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    domains = DomainPolicy([parsed.hostname or ""])
    domains.check(url)
    if browser_channel in {"chrome", "msedge"}:
        profile.mkdir(parents=True, exist_ok=True)
        # Human sign-in runs in a normal vendor browser with no automation or
        # remote-debugging connection. Only Derek's dedicated profile is used.
        process = subprocess.Popen([_installed_browser(browser_channel), "--user-data-dir=" + str(profile),
                                    "--no-first-run", "--no-default-browser-check", "--disable-background-mode", "--new-window", url],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("A normal browser opened with Derek's separate local profile.")
        input("Finish signing in, CLOSE all windows for this Derek profile, then press Enter here. ")
        try:
            code = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            raise AttentionRequired("Close all windows for the Derek browser profile before starting the companion worker.") from None
        if code != 0:
            raise AttentionRequired("The login browser did not exit normally. Close its windows and retry; sign-in success is not confirmed.")
        print("Manual browser session finished. Sign-in success must still be confirmed on the website.")
        return
    from playwright.sync_api import Error as PlaywrightError
    try:
        with persistent_browser(profile) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            input("Sign in manually in the dedicated browser. Press Enter here only after finishing sign-in. ")
    except PlaywrightError as exc:
        if type(exc).__name__ != "TargetClosedError":
            raise
        print("The login browser was closed. Run the login command again to continue; sign-in success has not been confirmed.")
