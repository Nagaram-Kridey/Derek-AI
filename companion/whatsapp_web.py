"""Dedicated Brave WhatsApp Web transport; no internal WhatsApp APIs or scripts.

The only send path receives already-confirmed typed arguments. Session cookies
stay in an isolated local profile. DOM observations never export chat history.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit, urlunsplit

from .browser import _installed_browser
from .journal import WorkerLock
from .policy import AttentionRequired, DomainPolicy, PolicyError
from .whatsapp import normalized

HOME = 'https://web.whatsapp.com/'
NETWORK_ROOTS = ('whatsapp.com', 'whatsapp.net', 'fbcdn.net')
COMPOSER = '#main footer [contenteditable="true"][role="textbox"]'
log = logging.getLogger(__name__)


def record(profile, state):
    """Persist only connection state, never page text, QR codes or cookies."""
    path = Path(profile).parent / 'whatsapp-web-status.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='whatsapp-status-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'state':state,'checked_at':datetime.now(timezone.utc).isoformat()}, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def profile_busy(profile):
    import psutil
    expected = os.path.normcase(str(Path(profile).resolve()))
    for process in psutil.process_iter(['name', 'cmdline']):
        try:
            if (process.info['name'] or '').lower() != 'brave.exe':
                continue
            for arg in process.info['cmdline'] or []:
                if arg.startswith('--user-data-dir='):
                    actual = os.path.normcase(str(Path(arg.split('=', 1)[1]).resolve()))
                    if actual == expected:
                        return True
        except (psutil.Error, OSError):
            continue
    return False


def status(profile):
    try:
        _installed_browser('brave')
        installed = True
    except RuntimeError:
        installed = False
    try:
        saved = json.loads((Path(profile).parent / 'whatsapp-web-status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    return {'browser':'brave', 'installed':installed, 'profile_exists':Path(profile).is_dir(),
            'browser_open':profile_busy(profile), 'state':saved.get('state','not_checked'),
            'checked_at':saved.get('checked_at')}


def open_login(profile):
    """Open a normal browser; the owner performs device linking manually."""
    profile = Path(profile)
    with WorkerLock(profile.parent / 'whatsapp-session'):
        if profile_busy(profile):
            return {'opened':False,'already_open':True}
        executable = _installed_browser('brave')
        profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen([executable, '--user-data-dir='+str(profile), '--no-first-run',
                          '--no-default-browser-check', '--disable-background-mode', '--new-window', HOME],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
    return {'opened':True,'already_open':False}


def network_url(url, validated=None):
    """Dedicated WhatsApp traffic, including encrypted WebSocket connections."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        allowed_port = parts.port in (None,443) or (
            parts.scheme=='wss' and host=='web.whatsapp.com' and parts.port==5222)
        if (parts.scheme not in {'https','wss'} or parts.username or parts.password
                or not allowed_port
                or not any(host == root or host.endswith('.'+root) for root in NETWORK_ROOTS)):
            raise PolicyError('WhatsApp requested an unapproved network destination.')
        https = urlunsplit(('https',host,parts.path,parts.query,''))
        if validated is None or host not in validated:
            DomainPolicy([host]).check(https)
            if validated is not None:
                validated.add(host)
    except ValueError:
        raise PolicyError('WhatsApp requested an invalid network destination.') from None


@contextmanager
def session(profile, check_interrupt=lambda:None):
    from playwright.sync_api import Error, sync_playwright
    profile = Path(profile)
    try:
        with WorkerLock(profile.parent / 'whatsapp-session'):
            if profile_busy(profile):
                raise AttentionRequired('WhatsApp browser busy. Close only Derek’s dedicated Brave windows, then submit a fresh request.')
            profile.mkdir(parents=True, exist_ok=True)
            with sync_playwright() as playwright:
                log.info('Opening dedicated Brave WhatsApp context')
                try:
                    log.info('Dedicated Brave context opened')
                    context = playwright.chromium.launch_persistent_context(
                        str(profile), executable_path=_installed_browser('brave'), headless=False,
                        service_workers='block', accept_downloads=False,
                        args=['--no-first-run','--no-default-browser-check'],
                        timeout=20000)
                except Error:
                    raise AttentionRequired('Brave could not open the WhatsApp profile. Close its dedicated windows and retry; the session was not reset.') from None
                try:
                    context.set_default_timeout(8000)
                    blocked = []
                    validated = set()
                    def route(request_route):
                        try:
                            network_url(request_route.request.url, validated)
                        except PolicyError:
                            blocked.append(True)
                            request_route.abort()
                        else:
                            request_route.continue_()
                    def websocket(ws):
                        try:
                            network_url(ws.url, validated)
                        except PolicyError:
                            blocked.append(True)
                            # An unconnected route is a local mock: no traffic
                            # reaches a server. Closing it synchronously from
                            # this callback can deadlock the handshake. Return,
                            # then let check() stop and close the whole context.
                            parts=urlsplit(ws.url)
                            log.warning('Blocked WhatsApp socket origin: %s %s %s',parts.scheme,parts.hostname,parts.port)
                        else:
                            ws.connect_to_server()
                    context.route('**/*', route)
                    context.route_web_socket('**/*', websocket)
                    page = context.pages[0] if context.pages else context.new_page()
                    for extra in context.pages[1:]:
                        extra.close()
                    def popup(opened):
                        blocked.append(True)
                        opened.close()
                    context.on('page', popup)
                    page.on('dialog', lambda dialog: (blocked.append(True), dialog.dismiss()))
                    page.on('download', lambda download: (blocked.append(True), download.cancel()))
                    def check():
                        check_interrupt()
                        if blocked:
                            raise AttentionRequired('WhatsApp opened an unexpected connection, dialog or window. No further input was issued.')
                        parsed = urlsplit(page.url)
                        if parsed.scheme!='https' or parsed.netloc!='web.whatsapp.com':
                            raise AttentionRequired('The browser left WhatsApp Web. Input stopped.')
                    log.info('Loading WhatsApp Web')
                    page.goto(HOME, wait_until='domcontentloaded', timeout=30000)
                    log.info('WhatsApp page loaded')
                    yield page, check
                except Error:
                    raise AttentionRequired('WhatsApp Web changed, disconnected or timed out. Inspect the dedicated browser and Activity; no automatic send retry.') from None
                finally:
                    log.info('Closing dedicated WhatsApp context')
                    try:
                        context.close()
                    except Error:
                        pass
                    log.info('Dedicated WhatsApp context closed')
    except RuntimeError:
        raise AttentionRequired('WhatsApp browser busy. Close Derek’s dedicated Brave windows and retry.') from None


def signed_in(page, check):
    for _ in range(40):
        check()
        side = page.locator('#side')
        if side.count()==1 and side.is_visible():
            return True
        if page.locator('[data-testid="qrcode"], canvas[aria-label*="Scan"]').count():
            return False
        if page.get_by_text('Log into WhatsApp',exact=True).count():
            return False
        page.wait_for_timeout(500)
    return False


def verify_header(page, recipient, check):
    check()
    header = page.locator('#main header').get_by_text(recipient, exact=True)
    if header.count()!=1 or not header.is_visible():
        raise AttentionRequired('WhatsApp Web recipient header does not uniquely match the confirmed name.')


def editor(page, recipient, check):
    verify_header(page, recipient, check)
    target = page.locator(COMPOSER)
    if target.count()!=1 or not target.is_visible() or not target.is_editable():
        raise AttentionRequired('The WhatsApp Web message box is not uniquely available.')
    if page.locator('#main footer [data-testid="quoted-message"], #main footer [aria-label="Cancel reply"]').count():
        raise AttentionRequired('An existing reply draft is open. It was preserved.')
    return target


def outgoing(page, message, *, _direction="out", _include_text=False):
    """Return stable rendered message IDs, never infer success from old text."""
    rows = page.locator('#main div[data-id]')
    if rows.count()>200:
        raise AttentionRequired('Unexpected WhatsApp message layout. Sending cannot be verified.')
    rendered = rows.all()
    # Grouped bubbles omit tails. Calibrate against explicit incoming/outgoing
    # bubbles in this same layout, rather than assuming right means outgoing.
    def edge(row):
        bubble = row.locator('[data-testid="msg-container"]')
        if bubble.count() != 1:
            return None
        box = bubble.bounding_box()
        return (box['x'], box['x'] + box['width']) if box else None

    anchors = {'in': [], 'out': []}
    for row in rendered:
        for direction in anchors:
            if row.locator(f'[data-icon="tail-{direction}"]').count():
                bounds = edge(row)
                if bounds:
                    anchors[direction].append(bounds)

    def grouped_outgoing(row):
        bounds = edge(row)
        if not bounds or not anchors['in'] or not anchors['out']:
            return False
        # A stable outgoing edge must differ from every incoming edge.
        for axis in (0, 1):
            outgoing_edges = [x[axis] for x in anchors[_direction]]
            incoming_edges = [x[axis] for x in anchors['in' if _direction == 'out' else 'out']]
            if (max(outgoing_edges) - min(outgoing_edges) <= 2
                    and all(abs(bounds[axis] - x) <= 2 for x in outgoing_edges)
                    and all(abs(bounds[axis] - x) > 20 for x in incoming_edges)):
                return True
        return False

    matches = {} if _include_text else set()
    for row in rendered:
        # Current WhatsApp Web uses an outgoing tail marker rather than a
        # message-out class or a true_ ID prefix. Keep exact legacy markers as
        # compatibility evidence, but never accept an incoming tail.
        if row.locator('[data-icon="tail-' + ('in' if _direction == 'out' else 'out') + '"]').count():
            continue
        own_class = ('message-' + _direction) in (row.get_attribute('class') or '').split()
        if not (own_class or row.locator('.message-' + _direction + ', [data-icon="tail-' + _direction + '"]').count() or grouped_outgoing(row)):
            continue
        texts = row.locator('[data-pre-plain-text] span.selectable-text').all_text_contents()
        if message is None or normalized(' '.join(texts)) == normalized(message):
            identifier = row.get_attribute('data-id')
            if identifier and len(identifier)<1000:
                if _include_text:
                    matches[hashlib.sha256(identifier.encode()).hexdigest()] = normalized(' '.join(texts))[:4000]
                else:
                    matches.add(identifier)
    return matches


def find_recipient(page, recipient, *, before_mutation, check):
    check()
    try:
        verify_header(page, recipient, check)
    except AttentionRequired:
        # Search is scoped to the dedicated sidebar; never global text matches.
        search = page.locator('#side').get_by_role('textbox')
        if search.count()!=1 or not search.is_visible():
            raise AttentionRequired('WhatsApp Web search is ambiguous or unavailable. No message was typed.')
        before_mutation(0)
        check()
        search.fill(recipient)
        page.wait_for_timeout(750)
        candidates = []
        for _ in range(12):
            check()
            # Message search hits repeat the contact's name but are not contact
            # tiles. Only actual chat/contact frames may become recipients.
            candidates = [item for item in page.locator('#pane-side [data-testid="cell-frame-container"] [data-testid="cell-frame-title"] span[title]').all()
                          if item.get_attribute('title')==recipient and normalized(item.inner_text())==recipient and item.is_visible()]
            if candidates:
                break
            page.wait_for_timeout(250)
        if len(candidates)!=1:
            raise AttentionRequired('No unique exact WhatsApp Web recipient. No message was typed.')
        check()
        candidates[0].click()
        page.wait_for_timeout(300)
    verify_header(page,recipient,check)


def send_on_page(page, args, *, before_mutation, check, progress=lambda stage:None):
    from desktop.message_guard import MessageGuard
    recipient, message = args['recipient'], args['message']
    MessageGuard(recipient, message)
    progress('searching')
    find_recipient(page,recipient,before_mutation=before_mutation,check=check)
    progress('recipient')
    target = editor(page, recipient, check)
    if normalized(target.inner_text()):
        raise AttentionRequired('An existing WhatsApp Web draft was preserved. Nothing was typed.')
    baseline = outgoing(page, message)
    before_mutation(0)
    target = editor(page, recipient, check)
    if normalized(target.inner_text()):
        raise AttentionRequired('The message box changed before typing. Existing draft preserved.')
    target.fill(message)
    progress('verifying')
    target = editor(page, recipient, check)
    if normalized(target.inner_text())!=normalized(message):
        raise AttentionRequired('The exact WhatsApp Web draft could not be verified. It was left unsent.')
    target.press('Enter')
    progress('checking')
    for _ in range(60):
        page.wait_for_timeout(250)
        target = editor(page, recipient, check)
        new = outgoing(page,message)-baseline
        if not normalized(target.inner_text()) and len(new)==1:
            return {'recipient':recipient,'transport':'brave_web','outgoing_verified':True,
                    'delivery_verified':False,'next_action':1,
                    'receipt_sha256':hashlib.sha256(next(iter(new)).encode()).hexdigest()}
    raise AttentionRequired('WhatsApp Web send result is uncertain. Inspect the chat; this message will not be retried.')


def send_web(args, *, profile, before_mutation, check_interrupt=lambda:None, progress=lambda stage:None):
    check_interrupt()
    progress('opening')
    with session(profile, check_interrupt) as (page, check):
        if not signed_in(page, check):
            record(profile,'relink_required')
            raise AttentionRequired('WhatsApp Web relink required. Open WhatsApp setup in Derek Settings, link it on your phone, then close the dedicated Brave window.')
        record(profile,'linked')
        return send_on_page(page,args,before_mutation=before_mutation,check=check,progress=progress)


def inspect(profile):
    with session(profile) as (page, check):
        linked = signed_in(page,check)
        record(profile,'linked' if linked else 'relink_required')
    return {'linked':linked,'input_sent':False}


def inspect_message(profile, recipient, message):
    """Inspect existing outgoing text; never fill a composer or issue Send.

    Matching history is not by itself proof that any particular stopped job
    succeeded. Report rendered timestamps for the owner to compare with Activity.
    """
    from desktop.message_guard import MessageGuard
    MessageGuard(recipient,message)
    with session(profile) as (page,check):
        if not signed_in(page,check):
            record(profile,'relink_required')
            raise AttentionRequired('WhatsApp Web relink required. Open setup in Settings.')
        record(profile,'linked')
        find_recipient(page,recipient,before_mutation=lambda _:None,check=check)
        matches=outgoing(page,message)
        receipts=[]
        for row in page.locator('#main div[data-id]').all():
            identifier=row.get_attribute('data-id')
            if identifier in matches:
                prefix=row.locator('[data-pre-plain-text]').first.get_attribute('data-pre-plain-text') or ''
                receipts.append({'receipt_sha256':hashlib.sha256(identifier.encode()).hexdigest(),
                                 'rendered_time':prefix.split(']')[0]+']' if prefix.startswith('[') and ']' in prefix else None})
        return {'recipient_verified':True,'composer_empty':not normalized(editor(page,recipient,check).inner_text()),
                'matching_outgoing':receipts,'message_typed':False,'send_issued':False,
                'delivery_verified':False}


if __name__=='__main__':
    import argparse
    from .config import Config
    parser=argparse.ArgumentParser(description='Dedicated Brave WhatsApp setup; sends nothing.')
    parser.add_argument('command',choices=['login','inspect','status','inspect-message'])
    parser.add_argument('--recipient')
    parser.add_argument('--message')
    options=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    profile=Config.from_env().whatsapp_profile
    try:
        if options.command=='inspect-message':
            if not options.recipient or not options.message:
                parser.error('inspect-message needs --recipient and --message.')
            result=inspect_message(profile,options.recipient,options.message)
        else:
            result={'login':open_login,'inspect':inspect,'status':status}[options.command](profile)
        print(json.dumps(result))
    except (AttentionRequired,RuntimeError) as exc:
        parser.exit(1,str(exc)+'\n')
