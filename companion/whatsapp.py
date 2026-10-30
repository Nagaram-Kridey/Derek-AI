"""Narrow native WhatsApp launcher, exact contact search and reviewed sender.

No history export, arbitrary keys, or automatic retry. Windows
OCR is local. Final input is journaled before dispatch and verified visually.
"""
import time
import re
from pathlib import Path

from desktop.observation import ObservationError, ObservationSession, windows, validate_scope
from desktop.visual_text import TextBox, exact_region_match
from .policy import AttentionRequired

WHATSAPP_APP_ID = '5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'


def whatsapp_windows():
    return [scope for scope,_ in windows()
            if Path(scope.executable).name.casefold()=='whatsapp.root.exe'
            and '5319275a.whatsappdesktop_' in scope.executable.casefold()]


def open_whatsapp(check_interrupt=lambda: None):
    """Launch only the installed package, then explicitly foreground its window.

    Avoid Windows Search typing: other search results must never become input
    targets. This activates the same installed app directly by its package ID.
    """
    import subprocess
    import os
    import win32gui
    import win32con
    from desktop.observation import unlocked
    check_interrupt()
    if not unlocked():
        raise AttentionRequired('Unlock Windows before opening WhatsApp.')
    choices=whatsapp_windows()
    if not choices:
        subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'),
                          'shell:AppsFolder\\'+WHATSAPP_APP_ID],shell=False)
    deadline=time.monotonic()+15
    while not choices and time.monotonic()<deadline:
        check_interrupt()
        if not unlocked():
            raise AttentionRequired('Windows locked during app startup.')
        time.sleep(.25)
        choices=whatsapp_windows()
    if len(choices)!=1:
        raise AttentionRequired('WhatsApp did not expose one unambiguous window. Open it manually.')
    scope=choices[0]
    validate_scope(scope)
    win32gui.ShowWindow(scope.hwnd,win32con.SW_MAXIMIZE)
    try:
        if win32gui.GetForegroundWindow()!=scope.hwnd:
            win32gui.SetForegroundWindow(scope.hwnd)
    except Exception:
        # Ask Windows to activate the installed app through its normal package
        # launcher. No synthetic Alt/Win keys, focus-lock changes or arbitrary
        # commands. A failed activation still stops before search or typing.
        subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'),
                          'shell:AppsFolder\\'+WHATSAPP_APP_ID],shell=False)
        deadline=time.monotonic()+5
        while win32gui.GetForegroundWindow()!=scope.hwnd and time.monotonic()<deadline:
            check_interrupt()
            validate_scope(scope)
            if not unlocked():
                raise AttentionRequired('Windows locked during app activation.')
            time.sleep(.2)
    if win32gui.GetForegroundWindow()!=scope.hwnd:
        raise AttentionRequired('WhatsApp could not take focus. Bring it to the front.')


def search_recipient(adapter, recipient):
    """Use the dedicated search box and reject duplicate/partial contact names."""
    width=adapter.bounds[2]-adapter.bounds[0]
    height=adapter.bounds[3]-adapter.bounds[1]
    if width<1100 or height<650:
        raise AttentionRequired('WhatsApp requires the maximized wide layout.')
    boxes=adapter.observe()
    # An already open, exactly verified conversation needs no search typing.
    # This also handles a retained search query from an earlier stopped run.
    try:
        layout(boxes,width,height,recipient)
    except AttentionRequired:
        pass
    else:
        return
    search=[b for b in boxes if normalized(b.text).casefold()=='search or start a new chat'
            and width*.03<b.left<width*.24 and 95<b.top<160]
    if len(search)!=1:
        raise AttentionRequired('The empty WhatsApp search field was not uniquely recognized. Clear search manually.')
    box=search[0]
    adapter.click(box.left+box.width/2,box.top+box.height/2)
    boxes=adapter.observe()
    # Check the search landmark after focusing before entering any query.
    def focused_search(frame):
        return any(normalized(b.text).casefold() in {
            'search or start a new chat','isearch or start a new chat','|search or start a new chat',
            # The full-window pass can join the magnifier icon (OCR "Q")
            # with otherwise exact placeholder text. The magnified pass may
            # merge the caret with S, so retain this independent exact read.
            'q search or start a new chat'}
            and width*.03<b.left<width*.24 and 95<b.top<160 for b in frame)
    for _ in range(3):
        if focused_search(boxes):
            break
        time.sleep(.2)
        boxes=adapter.observe()
    if not focused_search(boxes):
        raise AttentionRequired('Search focus could not be verified. Nothing was entered.')
    adapter.keys(recipient)
    time.sleep(.6)
    for _ in range(4):
        boxes=adapter.observe()
        headings=[b for b in boxes if normalized(b.text).casefold() in {'chats','contacts'}
                  and b.left<width*.24 and b.top>180]
        lower=min((b.top+b.height for b in headings),default=height)
        upper=min((b.top for b in boxes if normalized(b.text).casefold() in {
            'groups in common','messages','other contacts','global search'}
            and b.left<width*.24 and b.top>lower),default=height-100)
        matches=[b for b in boxes if normalized(b.text)==recipient
                 and width*.03<b.left and b.left+b.width<width*.24
                 and lower<b.top<upper]
        if len(matches)>1:
            raise AttentionRequired('Multiple exact recipient matches. Select the intended contact manually.')
        if len(matches)==1:
            result=matches[0]
            adapter.click(result.left+result.width/2,result.top+result.height/2)
            time.sleep(.3)
            boxes=adapter.observe()
            layout(boxes,width,height,recipient)
            return
        time.sleep(.25)
    raise AttentionRequired('No unique exact recipient result. No message was typed.')


def normalized(text):
    return ' '.join(text.replace('\u2019', "'").split())


def layout(boxes, width, height, recipient):
    """Supported wide desktop layout; never infer recipient from message bodies."""
    if width < 1100 or height < 650:
        raise AttentionRequired('Maximize WhatsApp; this adapter supports its wide desktop layout only.')
    header = (width * .25, 35, width * .75, 100)
    if not exact_region_match(boxes, recipient, header):
        raise AttentionRequired('The open WhatsApp header does not uniquely match the reviewed recipient.')
    return (width * .25, height - 90, width - 90, height - 5)


def region_text(boxes, region):
    left, top, right, bottom = region
    selected = [b for b in boxes if b.left >= left and b.top >= top
                and b.left+b.width <= right and b.top+b.height <= bottom]
    return normalized(' '.join(b.text for b in sorted(selected, key=lambda b: (b.top, b.left))))


def empty_composer(adapter, boxes, width, height, recipient):
    """Wait out caret OCR artifacts, but require an exact empty placeholder.

    Selecting a search result can focus the composer before our first read.
    Never treat the cursor-prefixed variants themselves as proof of emptiness.
    """
    caret_variants = {'tType a message', 'IType a message', 'Itype a message',
                      '|Type a message'}
    for attempt in range(6):
        composer = layout(boxes, width, height, recipient)
        text = region_text(boxes, composer)
        if text == 'Type a message':
            return boxes, composer
        if text not in caret_variants or attempt == 5:
            raise AttentionRequired('The WhatsApp composer is not provably empty. Existing drafts are preserved.')
        # Unequal delays avoid sampling the same phase of the blinking caret.
        time.sleep(.13 + attempt * .07)
        boxes = adapter.observe()


def outgoing_receipt_count(boxes, message, width, height):
    """Conservative single-line outgoing receipt; unknown themes fail closed."""
    matches=[]
    for box in boxes:
        text=normalized(box.text)
        # Only strip a trailing rendered clock/checkmark, never arbitrary text.
        text=re.sub(r'\s+\d{1,2}:\d{2}(?:\s*[✓✔]+)?$', '', text)
        if (text==normalized(message) and box.surface=='outgoing_green'
                and box.left>width*.55 and height*.65<box.top<height-90):
            matches.append(box)
    return len(matches)


def outgoing_receipt(boxes, message, width, height):
    return outgoing_receipt_count(boxes,message,width,height)==1


class NativeWhatsApp:
    def __init__(self, check_interrupt=lambda: None):
        import win32gui
        choices = whatsapp_windows()
        if len(choices) != 1:
            raise AttentionRequired('Open one signed-in WhatsApp Desktop window.')
        self.scope = choices[0]
        self.bounds = win32gui.GetWindowRect(self.scope.hwnd)
        self.check_interrupt = check_interrupt
        self.session = ObservationSession()
        self.observed_at = 0
        self.session.approve(self.scope)
        self.check()

    def check(self, local_only=False):
        import ctypes
        import win32gui
        if not local_only:
            self.check_interrupt()
        if ctypes.windll.user32.GetAsyncKeyState(27) & 0x8000:
            raise AttentionRequired('Escape pressed. Desktop input stopped; inspect the draft before retrying.')
        validate_scope(self.scope)
        if (win32gui.GetForegroundWindow() != self.scope.hwnd
                or win32gui.GetWindowRect(self.scope.hwnd) != self.bounds
                or time.monotonic() >= self.session.expires):
            raise AttentionRequired('WhatsApp lost focus, moved, or its local session expired. Inspect before retrying.')

    def observe(self):
        self.check()
        generation = self.session.start(visual=True)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.check(local_only=True)
            result = self.session.read_result(generation)
            if result is not None:
                if not result.get('ok'):
                    raise AttentionRequired('Local WhatsApp visual reading failed.')
                self.observed_at = result['observation'].get('captured_at', 0)
                return [TextBox(**box) for box in result['observation'].get('text_boxes', [])]
            time.sleep(.1)
        self.session.revoke()
        raise AttentionRequired('WhatsApp visual reading timed out.')

    def click(self, x, y):
        import win32gui
        import win32api
        import win32con
        self.check()
        point = (self.bounds[0]+int(x), self.bounds[1]+int(y))
        hit = win32gui.WindowFromPoint(point)
        if win32gui.GetAncestor(hit, win32con.GA_ROOT) != self.scope.hwnd:
            raise AttentionRequired('Another window covers the approved input target.')
        win32api.SetCursorPos(point)
        self.check()
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    def keys(self, text=None):
        import ctypes
        from ctypes import wintypes
        self.check(local_only=True)
        if time.monotonic()-self.observed_at > .75:
            raise AttentionRequired('The visual readback became stale before input. Inspect before retrying.')
        if any(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 for key in (16, 17, 18, 91, 92)):
            raise AttentionRequired('Release keyboard modifiers before desktop messaging.')
        class Keyboard(ctypes.Structure):
            _fields_ = [('vk', wintypes.WORD), ('scan', wintypes.WORD),
                        ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                        ('extra', ctypes.c_size_t)]
        class Mouse(ctypes.Structure):
            _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                        ('data', wintypes.DWORD), ('flags', wintypes.DWORD),
                        ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
        class Payload(ctypes.Union):
            _fields_ = [('keyboard', Keyboard), ('mouse', Mouse)]
        class Input(ctypes.Structure):
            _fields_ = [('type', wintypes.DWORD), ('payload', Payload)]
        events = []
        if text is None:
            events = [Input(1, Payload(keyboard=Keyboard(13, 0, f, 0, 0))) for f in (0, 2)]
        else:
            encoded = text.encode('utf-16-le')
            for offset in range(0, len(encoded), 2):
                unit = int.from_bytes(encoded[offset:offset+2], 'little')
                events.extend(Input(1, Payload(keyboard=Keyboard(0, unit, f, 0, 0))) for f in (4, 6))
        data = (Input * len(events))(*events)
        send = ctypes.windll.user32.SendInput
        send.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
        send.restype = wintypes.UINT
        if send(len(events), data, ctypes.sizeof(Input)) != len(events):
            raise AttentionRequired('Input was partial or uncertain. Inspect WhatsApp; do not replay this message.')

    def close(self):
        self.session.revoke()


def send_current(args, *, before_mutation, check_interrupt=lambda: None, adapter_factory=NativeWhatsApp, progress=lambda stage:None):
    recipient, message = args['recipient'], args['message']
    from desktop.message_guard import MessageGuard
    MessageGuard(recipient, message)  # Reject control characters before touching the desktop.
    navigating=args.get('open_and_search',False)
    if navigating:
        before_mutation(0)  # Search text/clicks are journaled too; never replay blindly.
        progress('opening')
        open_whatsapp(check_interrupt)
    adapter = adapter_factory(check_interrupt)
    try:
        if navigating:
            progress('searching')
            search_recipient(adapter,recipient)
        progress('recipient')
        width = adapter.bounds[2]-adapter.bounds[0]
        height = adapter.bounds[3]-adapter.bounds[1]
        boxes = adapter.observe()
        boxes, composer = empty_composer(adapter, boxes, width, height, recipient)
        placeholder = [b for b in boxes if normalized(b.text) == 'Type a message'
                       and b.left >= composer[0] and b.top >= composer[1]]
        if len(placeholder) != 1 or region_text(boxes, composer) != 'Type a message':
            raise AttentionRequired('The WhatsApp composer is not provably empty. Existing drafts are preserved.')
        # A fresh, confirmed command may intentionally repeat an earlier text.
        # Require an additional outgoing bubble; an old matching bubble alone
        # must never certify this send. The durable job journal prevents replay.
        previous_receipts = outgoing_receipt_count(boxes,message,width,height)
        if not navigating:
            before_mutation(0)  # Includes typing: a crash must never repeat or erase a draft.
        target = placeholder[0]
        # Magnified OCR can shift the placeholder's vertical box near the
        # window border. Click the center of the verified composer band.
        adapter.click(target.left+target.width/2, (composer[1]+composer[3])/2)
        focused = adapter.observe()
        focused_composer = layout(focused, width, height, recipient)
        # A blinking caret may merge with the placeholder in OCR. Wait for a
        # clean frame rather than accepting fuzzy text as proof of emptiness.
        for _ in range(3):
            if region_text(focused,focused_composer) in {'Type a message','IType a message','Itype a message','|Type a message','tType a message'}:
                break
            time.sleep(.2)
            focused=adapter.observe()
            focused_composer=layout(focused,width,height,recipient)
        if region_text(focused, focused_composer) not in {'Type a message','IType a message','Itype a message','|Type a message','tType a message'}:
            raise AttentionRequired('The chat or composer changed after focusing. Nothing was typed.')
        adapter.keys(message)
        progress('verifying')
        time.sleep(.4)
        boxes = adapter.observe()
        composer = layout(boxes, width, height, recipient)
        if region_text(boxes, composer) != normalized(message):
            raise AttentionRequired('Composed text could not be verified exactly. The draft was left unsent.')
        adapter.keys()  # Enter, only after exact visual readback.
        progress('checking')
        for _ in range(5):
            time.sleep(.5)
            boxes = adapter.observe()
            composer = layout(boxes, width, height, recipient)
            if region_text(boxes, composer) != 'Type a message':
                continue
            # Current adapter only accepts a new right-side outgoing text region.
            if outgoing_receipt_count(boxes, message, width, height)==previous_receipts+1:
                return {'recipient': recipient, 'outgoing_verified': True,
                        'delivery_verified': False, 'next_action': 1}
        raise AttentionRequired('Send result is uncertain. Inspect the chat; this message will not be retried.')
    except ObservationError:
        raise AttentionRequired('WhatsApp scope changed during visual verification.') from None
    finally:
        adapter.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read-only WhatsApp OCR compatibility check; sends nothing.')
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--inspect-current', help='Exact expected open conversation name')
    choice.add_argument('--find-recipient', help='Search/open this exact contact without typing a message or sending')
    options = parser.parse_args()
    native = NativeWhatsApp()
    try:
        if options.find_recipient:
            search_recipient(native,options.find_recipient)
            print({'recipient_verified':True,'message_typed':False,'message_sent':False})
        else:
            boxes = native.observe()
            width, height = native.bounds[2]-native.bounds[0], native.bounds[3]-native.bounds[1]
            boxes, composer = empty_composer(native, boxes, width, height, options.inspect_current)
            print({'header_verified': True, 'composer_empty': region_text(boxes, composer) == 'Type a message',
                   'local_ocr': True, 'input_sent': False})
    finally:
        native.close()
