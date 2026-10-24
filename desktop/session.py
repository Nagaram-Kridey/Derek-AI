"""Build a short-lived fragment handoff; never put the owner token in a URL."""
import json
import re
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from .credentials import read_owner_token

ORIGIN = 'http://127.0.0.1:8000'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def workspace_url():
    token = read_owner_token(ORIGIN)
    if not token:
        return ORIGIN
    request = Request(ORIGIN+'/v1/local/session/launch/',data=b'{}',method='POST',
                      headers={'Authorization':'Token '+token,'Content-Type':'application/json'})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=3) as response:
            data = json.loads(response.read(4096))
        code = data.get('code')
        if isinstance(code,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',code):
            return ORIGIN+'/#desktop-session='+code
    except (OSError,ValueError):
        pass
    return ORIGIN
