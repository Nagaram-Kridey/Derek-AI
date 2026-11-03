"""Private API responses and narrow capabilities for the local workspace."""

from django.conf import settings
from django.utils.cache import patch_vary_headers


class WorkspaceHeaders:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Referrer-Policy"] = "no-referrer"
        response["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
        if request.path.startswith("/v1/") or request.path == "/v1/turn":
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
            patch_vary_headers(response, ["Authorization"])
        if request.path == "/":
            # Keep the GIS popup's opener channel available for its callback.
            response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
            # GIS needs the document's origin when running on local HTTP.
            # API responses still suppress referrers entirely.
            response["Referrer-Policy"] = "no-referrer-when-downgrade" if settings.DEBUG else "strict-origin-when-cross-origin"
            response["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; img-src 'self' data: blob: https://www.gstatic.com; font-src 'self'; connect-src 'self' https://accounts.google.com/gsi/; frame-src 'self' https://accounts.google.com/gsi/; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
        return response
