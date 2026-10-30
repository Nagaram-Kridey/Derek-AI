"""Read-only per-window observations. Optional ephemeral OCR; no input or transport."""
from dataclasses import asdict, dataclass
import multiprocessing
import json
import queue
import threading
from pathlib import Path
import time

BLOCKED = {'chrome.exe','msedge.exe','firefox.exe','brave.exe','opera.exe','iexplore.exe',
           'windowsterminal.exe','cmd.exe','powershell.exe','pwsh.exe','conhost.exe',
           'keepass.exe','keepassxc.exe','1password.exe','bitwarden.exe','credentialuibroker.exe',
           'consent.exe','logonui.exe','winlogon.exe','mstsc.exe','code.exe','devenv.exe','msedgewebview2.exe'}
SENSITIVE_TITLES = ('password','sign in','sign-in','log in','login','authentication','credentials','payment','banking')


class ObservationError(ValueError):
    pass


@dataclass(frozen=True)
class WindowScope:
    hwnd: int
    pid: int
    started: float
    executable: str


def unlocked():
    import win32con
    import win32service
    desktop = None
    try:
        desktop = win32service.OpenInputDesktop(0, False, win32con.DESKTOP_READOBJECTS)
        return win32service.GetUserObjectInformation(desktop,win32con.UOI_NAME).lower() == 'default'
    except Exception:
        return False
    finally:
        if desktop:
            desktop.CloseDesktop()


def identity(hwnd):
    import psutil
    import win32gui
    import win32process
    if not unlocked() or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
        raise ObservationError('The selected window is unavailable or Windows is locked.')
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = psutil.Process(pid)
    import win32api
    import win32con
    import win32security
    handle = win32api.OpenProcess(0x1000,False,pid)
    try:
        token=win32security.OpenProcessToken(handle,win32con.TOKEN_QUERY)
        try:
            if win32security.GetTokenInformation(token,win32security.TokenElevation):
                raise ObservationError('Elevated applications are excluded from observation.')
        finally:
            token.Close()
    finally:
        handle.Close()
    executable = str(Path(process.exe()).resolve())
    title = win32gui.GetWindowText(hwnd)
    if Path(executable).name.lower() in BLOCKED or any(word in title.lower() for word in SENSITIVE_TITLES):
        raise ObservationError('This app is excluded from screen observation. Use approved browser workflows for browser tasks.')
    return WindowScope(hwnd, pid, process.create_time(), executable)


def validate_scope(scope):
    try:
        if identity(scope.hwnd) != scope:
            raise ObservationError('The selected application instance changed. Approve it again.')
    except ObservationError:
        raise
    except Exception:
        raise ObservationError('The selected application is no longer accessible.') from None


def windows():
    import win32gui
    choices=[]
    def visit(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                scope = identity(hwnd)
                choices.append((scope,win32gui.GetWindowText(hwnd)[:160]))
        except Exception:
            pass
    win32gui.EnumWindows(visit,None)
    return choices[:60]


def element_data(element, number):
    if element.CurrentIsPassword:
        return {'id':number,'role':'protected','name':'[protected control omitted]','patterns':[]}
    rect=element.CurrentBoundingRectangle
    return {'id':number,'role':(element.CurrentLocalizedControlType or '')[:60],
            'name':(element.CurrentName or '')[:250],
            'patterns':[label for label,prop in [('invoke',30031),('scroll',30034),('value',30043)] if element.GetCurrentPropertyValue(prop)],
            'bounds':[rect.left,rect.top,rect.right,rect.bottom]}


def scoped_processes(scope):
    """WhatsApp hosts its controls in owned WebView children, not the root PID."""
    import psutil
    allowed={scope.pid:scope.started}
    if Path(scope.executable).name.lower()=='whatsapp.root.exe':
        for child in psutil.Process(scope.pid).children(recursive=True):
            if child.name().lower()=='msedgewebview2.exe':
                allowed[child.pid]=child.create_time()
    return allowed


def process_matches(pid, allowed):
    import psutil
    try:
        return pid in allowed and psutil.Process(pid).create_time()==allowed[pid]
    except psutil.Error:
        return False


def read_elements(scope):
    """UIA APIs are read only here; protected elements are skipped before names."""
    validate_scope(scope)
    allowed=scoped_processes(scope)
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    try:
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen import UIAutomationClient as uia
        automation = comtypes.client.CreateObject(uia.CUIAutomation,interface=uia.IUIAutomation)
        root = automation.ElementFromHandle(scope.hwnd)
        walker = automation.ControlViewWalker
        queue, result, budget = [(root,0)], [], 16000
        deadline = time.monotonic()+3
        while queue and len(result)<80 and budget>0 and time.monotonic()<deadline:
            element, depth=queue.pop(0)
            if not process_matches(element.CurrentProcessId,allowed):
                continue
            if element.CurrentIsPassword:
                result.append(element_data(element,len(result)+1))
                continue
            item=element_data(element,len(result)+1)
            budget -= len(item['name'])+len(item['role'])
            result.append(item)
            if depth<6:
                child=walker.GetFirstChildElement(element)
                count=0
                while child and count<80 and len(queue)<160:
                    queue.append((child,depth+1)); count+=1
                    child=walker.GetNextSiblingElement(child)
        validate_scope(scope)
        return {'elements':result,'limited':bool(queue),'local_only':True,'input_enabled':False}
    finally:
        comtypes.CoUninitialize()


def worker(scope_data, pipe, visual=False):
    try:
        scope=WindowScope(**scope_data)
        if visual:
            import asyncio
            from .visual_text import capture_approved_window, recognize
            image=capture_approved_window(scope)
            captured_at=time.monotonic()
            try:
                boxes=asyncio.run(recognize(image))
                # Small dark-theme composer text is unreliable in a full-window
                # OCR pass. Read that bounded region at twice its native size.
                if image.width>=1100:
                    from .visual_text import TextBox
                    left,top=int(image.width*.28),image.height-90
                    crop=image.crop((left,top,image.width-90,image.height-5))
                    scale=min(3,4096//crop.width)
                    enlarged=crop.resize((crop.width*scale,crop.height*scale))
                    try:
                        detail=asyncio.run(recognize(enlarged))
                        boxes=[b for b in boxes if not (b.left>=left and b.top>=top)]
                        boxes.extend(TextBox(b.text,left+b.left/scale,top+b.top/scale,
                                             b.width/scale,b.height/scale,b.surface) for b in detail)
                    finally:
                        crop.close();enlarged.close()
                    # The sidebar search placeholder is also small, dark UI
                    # text. Restrict magnification to its text area, excluding
                    # the magnifying-glass icon and chat history below it.
                    left,top=int(image.width*.067),105
                    right,bottom=int(image.width*.22),155
                    crop=image.crop((left,top,right,bottom))
                    enlarged=crop.resize((crop.width*3,crop.height*3))
                    try:
                        detail=asyncio.run(recognize(enlarged))
                        boxes=[b for b in boxes if not (left<=b.left<right and top<=b.top<bottom)]
                        boxes.extend(TextBox(b.text,left+b.left/3,top+b.top/3,
                                             b.width/3,b.height/3,b.surface) for b in detail)
                    finally:
                        crop.close();enlarged.close()
            finally:
                image.close()
            validate_scope(scope)
            observation={'elements':[], 'text_boxes':[asdict(box) for box in boxes],
                         'local_only':True, 'input_enabled':False, 'visual':True,
                         'captured_at':captured_at}
        else:
            observation=read_elements(scope)
        pipe.send_bytes(json.dumps({'ok':True,'observation':observation}).encode())
    except Exception:
        pipe.send_bytes(b'{"ok":false}')
    finally:
        pipe.close()


class ObservationSession:
    """Explicit local consent, in-memory expiry and a killable UIA reader."""
    def __init__(self):
        self.scope=None
        self.expires=0
        self.process=None
        self.pipe=None
        self.generation=0
        self.results=None

    def approve(self, scope):
        self.revoke()
        validate_scope(scope)
        self.scope=scope
        self.expires=time.monotonic()+120

    def start(self, visual=False):
        if self.scope is None or time.monotonic()>=self.expires:
            self.revoke()
            raise ObservationError('Approve an application for a new two-minute session.')
        validate_scope(self.scope)
        if self.process is not None:
            raise ObservationError('An observation is already running.')
        context=multiprocessing.get_context('spawn')
        parent, child=context.Pipe(duplex=False)
        process=context.Process(target=worker,args=(asdict(self.scope),child,visual),daemon=True)
        try:
            process.start()
        except Exception:
            parent.close();child.close()
            if process.pid and process.is_alive():
                process.terminate();process.join(timeout=1)
            raise ObservationError('The local reader could not start. Reapprove the application and retry.') from None
        child.close()
        results=queue.Queue(maxsize=1)
        def receive():
            try:
                # Only this owned worker writes the pipe. Bound bytes before JSON
                # decoding and never wait for a partially sent frame on Tk.
                result=json.loads(parent.recv_bytes(65536))
                if not isinstance(result,dict): result={'ok':False}
            except Exception:
                result={'ok':False}
            try: results.put_nowait(result)
            except queue.Full: pass
        self.pipe=parent;self.process=process;self.results=results
        self.generation+=1
        threading.Thread(target=receive,daemon=True,name='derek-observation-reader').start()
        return self.generation

    def read_result(self, generation):
        if generation != self.generation or self.process is None:
            return None
        if self.scope is None or time.monotonic()>=self.expires:
            self.revoke()
            raise ObservationError('Observation permission expired.')
        validate_scope(self.scope)
        try:
            result=self.results.get_nowait()
        except queue.Empty:
            return None
        # A lock/scope change after the worker read must also prevent display.
        validate_scope(self.scope)
        if time.monotonic()>=self.expires:
            self.revoke()
            raise ObservationError('Observation permission expired.')
        self.process.join(timeout=1)
        if self.process.is_alive():
            self.process.terminate(); self.process.join(timeout=1)
        self.pipe.close();self.pipe=None;self.process=None;self.results=None
        validate_scope(self.scope)
        if time.monotonic()>=self.expires:
            self.revoke()
            raise ObservationError('Observation permission expired.')
        return result

    def revoke(self):
        self.generation+=1
        self.scope=None; self.expires=0
        if self.process:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill(); self.process.join(timeout=1)
        if self.pipe: self.pipe.close()
        self.process=None; self.pipe=None;self.results=None
