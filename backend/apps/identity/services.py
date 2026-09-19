import hashlib
import secrets
import string
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.identity.exceptions import (
    AccountSuspendedError,
    AlreadyVerifiedError,
    IdentifierTakenError,
    InvalidCredentialsError,
    RefreshTokenExpiredError,
    RefreshTokenInvalidError,
    RefreshTokenRevokedError,
    UserNotFoundError,
    VerificationCodeExpiredError,
    VerificationCodeInvalidError,
)
from apps.identity.models import (
    AccountStatus,
    RefreshToken,
    User,
    VerificationCode,
    VerificationStatus,
)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_numeric_code(length: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


class NotificationGateway:
    """
    Minimal development-mode notification gateway. Building a full
    Email/SMS provider integration is explicitly out of scope for TASK 1.
    This stub satisfies FLOW-AUTH-01 ("إرسال كود تحقق") by making the
    verification code observable via structured logging, without
    introducing external infrastructure.
    """

    def send_verification_code(self, user: User, raw_code: str) -> None:
        import logging

        logger = logging.getLogger("apps.identity.notifications")
        destination = user.email or user.phone
        logger.info(
            "Verification code issued: user_id=%s destination=%s code=%s",
            user.id, destination, raw_code,
        )


notification_gateway = NotificationGateway()


class AuthService:
    """Application-layer authentication and account lifecycle logic (Phase 6 §5)."""

    @staticmethod
    def _identifier_exists(email, phone) -> bool:
        filters = Q()
        if email:
            filters |= Q(email__iexact=email)
        if phone:
            filters |= Q(phone=phone)
        if not filters:
            return False
        return User.objects.filter(filters).exists()

    @classmethod
    @transaction.atomic
    def register(cls, email, phone, password: str):
        email_normalized = User.objects.normalize_email(email) if email else None

        if cls._identifier_exists(email_normalized, phone):
            raise IdentifierTakenError()

        try:
            user = User.objects.create_user(
                email=email_normalized, phone=phone, password=password
            )
        except IntegrityError:
            raise IdentifierTakenError()

        raw_code = cls._issue_verification_code(user)
        notification_gateway.send_verification_code(user, raw_code)

        return user, raw_code

    @classmethod
    def _issue_verification_code(cls, user: User) -> str:
        raw_code = _generate_numeric_code(settings.VERIFICATION_CODE_LENGTH)
        expires_at = timezone.now() + timedelta(
            minutes=settings.VERIFICATION_CODE_LIFETIME_MINUTES
        )
        VerificationCode.objects.create(
            user=user,
            code_hash=_hash_value(raw_code),
            purpose=VerificationCode.Purpose.REGISTRATION,
            expires_at=expires_at,
        )
        return raw_code

    @classmethod
    @transaction.atomic
    def verify(cls, user_id, code: str) -> User:
        try:
            user = User.objects.select_for_update().get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise UserNotFoundError()

        if user.verification_status == VerificationStatus.VERIFIED:
            raise AlreadyVerifiedError()

        verification = (
            VerificationCode.objects.select_for_update()
            .filter(
                user=user,
                purpose=VerificationCode.Purpose.REGISTRATION,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if verification is None:
            raise VerificationCodeInvalidError()

        if verification.is_expired():
            raise VerificationCodeExpiredError()

        if verification.attempts >= settings.VERIFICATION_MAX_ATTEMPTS:
            raise VerificationCodeInvalidError()

        if verification.code_hash != _hash_value(code):
            verification.attempts += 1
            verification.save(update_fields=["attempts"])
            raise VerificationCodeInvalidError()

        verification.consumed_at = timezone.now()
        verification.save(update_fields=["consumed_at"])

        user.verification_status = VerificationStatus.VERIFIED
        user.account_status = AccountStatus.ACTIVE
        user.save(update_fields=["verification_status", "account_status", "updated_at"])

        return user

    @classmethod
    def authenticate(cls, identifier: str, password: str) -> User:
        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(phone=identifier).first()
        )

        if user is None or not user.check_password(password):
            raise InvalidCredentialsError()

        if user.account_status == AccountStatus.SUSPENDED:
            raise AccountSuspendedError()

        if user.account_status == AccountStatus.UNVERIFIED:
            raise InvalidCredentialsError()

        return user

    @classmethod
    def issue_access_token(cls, user: User) -> str:
        now = timezone.now()
        expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
        payload = {
            "sub": str(user.id),
            "role": user.role,
            "token_type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @classmethod
    @transaction.atomic
    def issue_refresh_token(cls, user: User) -> str:
        raw_token = secrets.token_urlsafe(64)
        expires_at = timezone.now() + timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS)
        RefreshToken.objects.create(
            user=user,
            token_hash=_hash_value(raw_token),
            expires_at=expires_at,
        )
        return raw_token

    @classmethod
    def issue_token_pair(cls, user: User):
        access_token = cls.issue_access_token(user)
        refresh_token = cls.issue_refresh_token(user)
        return access_token, refresh_token

    @classmethod
    @transaction.atomic
    def rotate_refresh_token(cls, raw_refresh_token: str):
        token_hash = _hash_value(raw_refresh_token)

        try:
            stored_token = (
                RefreshToken.objects.select_for_update()
                .select_related("user")
                .get(token_hash=token_hash)
            )
        except RefreshToken.DoesNotExist:
            raise RefreshTokenInvalidError()

        if stored_token.revoked:
            raise RefreshTokenRevokedError()

        if stored_token.is_expired():
            raise RefreshTokenExpiredError()

        user = stored_token.user

        if user.account_status == AccountStatus.SUSPENDED:
            raise AccountSuspendedError()

        stored_token.revoked = True
        stored_token.save(update_fields=["revoked"])

        return cls.issue_token_pair(user)

    @classmethod
    @transaction.atomic
    def revoke_refresh_token(cls, raw_refresh_token: str, user: User = None) -> None:
        token_hash = _hash_value(raw_refresh_token)

        try:
            stored_token = RefreshToken.objects.select_for_update().get(token_hash=token_hash)
        except RefreshToken.DoesNotExist:
            raise RefreshTokenInvalidError()

        if user is not None and stored_token.user_id != user.id:
            raise RefreshTokenInvalidError()

        stored_token.revoked = True
        stored_token.save(update_fields=["revoked"])