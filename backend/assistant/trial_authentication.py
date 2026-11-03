"""Apply invitation revocation even on endpoints with explicit permission classes."""
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .permissions import trial_admitted


class WorkspaceTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not trial_admitted(user):
            raise AuthenticationFailed("This account is not invited to this testing workspace.")
        return user, token
