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
    visual=tk.BooleanVar(value=False)
    status=tk.StringVar(value='Screen observation is off. Enable this session to select an app.')
    frame=ttk.Frame(root,padding=18); frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Screen access · local preview',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Read one approved app for two minutes. Optional WhatsApp visual reading uses an in-memory window image and local Windows OCR.\nPreview stays here. No model uploads, clicks or typing.',wraplength=760).pack(anchor='w',pady=10)
    ttk.Checkbutton(frame,text='1. Enable screen observation for this session',variable=enabled,command=lambda:refresh()).pack(anchor='w',pady=8)
    ttk.Checkbutton(frame,text='Use local visual text reading (WhatsApp Desktop only)',variable=visual,command=lambda:revoke()).pack(anchor='w')
    ttk.Label(frame,text='2. Select an app below, approve it, then read its controls.').pack(anchor='w')
    selector=ttk.Combobox(frame,state='disabled',width=100); selector.pack(fill='x',pady=8)
    output=tk.Text(frame,wrap='word',height=20,state='disabled')
    buttons=ttk.Frame(frame); buttons.pack(fill='x',pady=8)
    def clear():
        output.configure(state='normal'); output.delete('1.0','end');
        output.insert('1.0','No screen data has been read.\n\nEnable this session, choose an app, and approve it before reading.\n\nThis preview lists accessible controls or optional local WhatsApp visual text. It does not send messages.\nKnown browsers and terminals are excluded. Use browser workflows for websites.');output.configure(state='disabled')
    def revoke():
        session.revoke(); clear()
        read_button.configure(state='disabled')
        approve_button.configure(state='normal' if enabled.get() and selector.current()>=0 else 'disabled')
        status.set('Permission revoked. Approve an app again to observe it.')
    def refresh():
        nonlocal choices
        revoke()
        try:
            choices=windows() if enabled.get() else []
            selector.configure(values=[f'{title} · PID {scope.pid}' for scope,title in choices],state='readonly' if enabled.get() else 'disabled')
            selector.set('')
            approve_button.configure(state='disabled')
            status.set((f'{len(choices)} eligible app windows. Choose one, then approve local reading.' if choices else 'No eligible app windows. Open a supported app such as Notepad, then refresh. Known browsers and terminals are excluded.') if enabled.get() else 'Screen observation is off. Enable the checkbox above to begin.')
        except Exception:
            choices=[];status.set('Window inventory unavailable. Unlock Windows and try again.')
    def approve():
        try:
            if not enabled.get() or selector.current()<0: raise ObservationError('Select an app first.')
            session.approve(choices[selector.current()][0])
            read_button.configure(state='normal')
            clear();status.set('Approved for two minutes. Select Read selected app for a local preview.')
        except Exception as exc:
            revoke();status.set(str(exc) if isinstance(exc,ObservationError) else 'Approval failed. Refresh the app list.')
    def read():
        try:
            generation=session.start(visual=visual.get());clear()
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
                        observation=result['observation']
                        meaningful=[e for e in observation['elements'] if e.get('role') not in {'window','pane','title bar','menu bar'}]
                        output.configure(state='normal');output.delete('1.0','end')
                        if not meaningful and not observation.get('visual'):
                            output.insert('1.0','This app exposes no usable accessible controls.\nFor WhatsApp Desktop, select local visual text reading and approve again.\n\n')
                        output.insert('end',json.dumps(observation,indent=2));output.configure(state='disabled')
                        count=len(observation.get('text_boxes',observation['elements']))
                        status.set(f"{count} items read locally. No data was sent to Derek models or Telegram.")
                    else:
                        revoke();status.set('Observation unavailable. Refresh and approve the window again.')
                    return
                if time.monotonic()>deadline:
                    revoke();status.set('The observation timed out. Permission was revoked.');return
                root.after(100,poll)
            root.after(100,poll)
        except ObservationError as exc: status.set(str(exc))
    ttk.Button(buttons,text='Refresh apps',command=refresh).pack(side='left')
    approve_button=ttk.Button(buttons,text='Approve selected app',command=approve,state='disabled');approve_button.pack(side='left',padx=6)
    read_button=ttk.Button(buttons,text='Read selected app',command=read,state='disabled');read_button.pack(side='left')
    ttk.Button(buttons,text='STOP / revoke',command=revoke).pack(side='right')
    output.pack(fill='both',expand=True,pady=12)
    clear()
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
