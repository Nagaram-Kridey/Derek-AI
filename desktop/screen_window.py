"""Local consent and preview for read-only Windows UI observations."""
import json
import time
import tkinter as tk
from tkinter import ttk
from .observation import ObservationError, ObservationSession, windows


def main():
    root=tk.Tk(); root.title('Derek · Screen observation'); root.geometry('820x640')
    session=ObservationSession(); choices=[]
    enabled=tk.BooleanVar(value=False)
    status=tk.StringVar(value='Screen observation is off. Enable this session to select an app.')
    frame=ttk.Frame(root,padding=18); frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Screen access · local preview',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Read accessible control names from one approved app for two minutes.\nPreview stays in this window. No screenshots, model uploads, clicks or typing.',wraplength=760).pack(anchor='w',pady=10)
    selector=ttk.Combobox(frame,state='disabled',width=100); selector.pack(fill='x',pady=8)
    output=tk.Text(frame,wrap='word',height=20,state='disabled')
    buttons=ttk.Frame(frame); buttons.pack(fill='x',pady=8)
    def clear():
        output.configure(state='normal'); output.delete('1.0','end'); output.configure(state='disabled')
    def revoke():
        session.revoke(); clear()
        status.set('Permission revoked. Approve an app again to observe it.')
    def refresh():
        nonlocal choices
        revoke()
        try:
            choices=windows() if enabled.get() else []
            selector.configure(values=[f'{title} · PID {scope.pid}' for scope,title in choices],state='readonly' if enabled.get() else 'disabled')
            selector.set('')
            status.set('Choose an app, then approve local reading. Known browsers, terminals and sensitive apps are excluded.' if enabled.get() else 'Screen observation is off.')
        except Exception:
            choices=[];status.set('Window inventory unavailable. Unlock Windows and try again.')
    def approve():
        try:
            if not enabled.get() or selector.current()<0: raise ObservationError('Select an app first.')
            session.approve(choices[selector.current()][0])
            clear();status.set('Approved for two minutes. Select Read selected app for a local preview.')
        except Exception as exc:
            revoke();status.set(str(exc) if isinstance(exc,ObservationError) else 'Approval failed. Refresh the app list.')
    def read():
        try:
            generation=session.start();clear()
            process=session.process
            deadline=time.monotonic()+5
            status.set('Reading the approved window…')
            def poll():
                if session.generation != generation or session.process is not process: return
                if time.monotonic()>deadline:
                    revoke();status.set('The observation timed out. Permission was revoked.');return
                if time.monotonic()>=session.expires:
                    revoke();status.set('Consent expired. Approve the application again.');return
                try:
                    result=session.read_result(generation)
                except (ObservationError,EOFError,OSError):
                    revoke();status.set('Window state changed or permission was lost. Approve it again.');return
                if result is not None:
                    if time.monotonic()>deadline:
                        revoke();status.set('The observation timed out. Permission was revoked.');return
                    if result.get('ok'):
                        output.configure(state='normal');output.insert('1.0',json.dumps(result['observation'],indent=2));output.configure(state='disabled')
                        status.set('Local preview only. No data was sent to Derek models or Telegram.')
                    else:
                        revoke();status.set('Observation unavailable. Refresh and approve the window again.')
                    return
                if time.monotonic()>deadline:
                    revoke();status.set('The observation timed out. Permission was revoked.');return
                root.after(100,poll)
            root.after(100,poll)
        except ObservationError as exc: status.set(str(exc))
    ttk.Checkbutton(frame,text='Enable read-only observation for this local session',variable=enabled,command=refresh).pack(anchor='w')
    ttk.Button(buttons,text='Refresh apps',command=refresh).pack(side='left')
    ttk.Button(buttons,text='Approve selected app',command=approve).pack(side='left',padx=6)
    ttk.Button(buttons,text='Read selected app',command=read).pack(side='left')
    ttk.Button(buttons,text='STOP / revoke',command=revoke).pack(side='right')
    output.pack(fill='both',expand=True,pady=12)
    ttk.Label(frame,textvariable=status,wraplength=760).pack(anchor='w')
    selector.bind('<<ComboboxSelected>>',lambda _:revoke())
    def expire():
        if session.scope and time.monotonic()>=session.expires:
            revoke();status.set('Two-minute permission expired. Preview cleared.')
        root.after(500,expire)
    def close(): session.revoke();root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);root.bind('<Escape>',lambda _:revoke());root.after(500,expire);root.mainloop()


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
