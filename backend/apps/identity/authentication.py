import jwt
from django.conf import settings
from rest_framework import authentication

from apps.identity.exceptions import AccessTokenInvalidError
from apps.identity.models import User


class JWTAuthentication(authentication.BaseAuthentication):
    """
    Stateless JWT access-token authentication (Phase 6 §7.K). Refresh tokens
    are never accepted here — only short-lived access tokens signed with
    JWT_SECRET_KEY.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        raw_token = parts[1]
        payload = self._decode(raw_token)

        if payload.get("token_type") != "access":
            raise AccessTokenInvalidError()

        user_id = payload.get("sub")
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise AccessTokenInvalidError()

        return (user, payload)

    def _decode(self, raw_token):
        try:
            return jwt.decode(
                raw_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.InvalidTokenError:
            raise AccessTokenInvalidError()

    def authenticate_header(self, request):
        return self.keyword