"""Private API responses and narrow capabilities for the local workspace."""

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
            response["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://www.gstatic.com; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
        return response
