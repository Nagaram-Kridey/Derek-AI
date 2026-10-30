"""Single-thread session owner: reads only explicit watches, serializes sends."""
import time
from . import whatsapp_web as web
from .policy import AttentionRequired


class Monitor:
    def __init__(self, config, client):
        self.config, self.client = config, client
        self.context = self.page = self.guard = None
        self.interrupt = self.check_global
        self.next_poll = 0
        self.cursor = 0

    def check_global(self):
        from .desktop_state import desktop_unlocked
        if not desktop_unlocked() or self.client.heartbeat().get('paused'):
            raise AttentionRequired('WhatsApp monitoring paused.')

    def close(self):
        if self.context:
            try:
                self.context.__exit__(None, None, None)
            finally:
                self.context = self.page = self.guard = None

    def open(self):
        if self.context:
            self.guard()
            return
        context = web.session(self.config.whatsapp_profile, lambda: self.interrupt())
        page, guard = context.__enter__()
        self.context, self.page, self.guard = context, page, guard
        if not web.signed_in(page, guard):
            self.close()
            raise AttentionRequired('WhatsApp needs manual relinking in Settings.')
        web.record(self.config.whatsapp_profile, 'linked')

    def send(self, args, *, before_mutation, check_interrupt, progress, **kwargs):
        self.interrupt = check_interrupt
        try:
            self.open()
            return web.send_on_page(self.page, args, before_mutation=before_mutation,
                                    check=self.guard, progress=progress)
        except Exception:
            self.close()
            raise
        finally:
            self.interrupt = self.check_global

    def poll(self):
        if time.monotonic() < self.next_poll:
            return
        self.next_poll = time.monotonic() + 5
        watches = self.client.post('/v1/desktop/whatsapp/sync/', {}).get('watches', [])
        if not watches:
            self.close()
            return
        watch = watches[self.cursor % len(watches)]
        self.cursor += 1
        endpoint = '/v1/desktop/whatsapp/' + watch['id'] + '/observe/'
        try:
            self.open()
            # Revalidate the watch immediately before navigating/reading.
            current = self.client.post('/v1/desktop/whatsapp/sync/', {}).get('watches', [])
            if watch['id'] not in {x['id'] for x in current}:
                return
            web.find_recipient(self.page, watch['recipient'], before_mutation=lambda _: None, check=self.guard)
            messages = web.outgoing(self.page, None, _direction='in', _include_text=True)
            self.client.post(endpoint, {'messages': [{'receipt': key, 'text': text} for key, text in messages.items()]})
        except Exception:
            self.close()
            self.next_poll = time.monotonic() + 30
            # Never expose page contents or provider exception bodies.
            self.client.post(endpoint, {'state': 'needs_attention', 'messages': []})
