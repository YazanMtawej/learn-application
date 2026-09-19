import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.identity.managers import UserManager


class Role(models.TextChoices):
    STUDENT = "student", "Student"
    INSTRUCTOR = "instructor", "Instructor"
    ORGANIZATION = "organization", "Organization"
    ADMIN = "admin", "Admin"


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    VERIFIED = "verified", "Verified"


class AccountStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class User(AbstractBaseUser):
    """
    Identity & Access — User entity.
    Schema reference: PHASE_8_DATABASE_DESIGN.md §4.1 `users` table.

    Field provenance:
    - id, email, phone, role, verification_status, account_status:
      CONFIRMED — Phase 8 §4.1 `users` table, verbatim.
    - password: CONFIRMED field concept (Phase 8 names the column
      `password_hash`); the Django attribute name `password` is required
      by AbstractBaseUser internals (set_password/check_password), so the
      DB column is remapped via db_column to match the approved schema
      exactly while keeping the attribute name Django expects.
    - is_staff, last_login: NOT in Phase 8 schema. Required by Django's
      auth/admin machinery given the choice to use AbstractBaseUser +
      Django admin. Framework necessity, not a domain decision — never
      exposed via any API contract.
    - created_at, updated_at: NOT in Phase 8 schema for `users`
      specifically. Kept as low-risk operational metadata, never exposed
      via any API response. Not covered by owner decisions G1-G5; left
      as a minor non-blocking addition.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Django requires the attribute name "password" (AbstractBaseUser
    # internals reference self.password directly). db_column remaps the
    # actual database column to match Phase 8 §4.1 ("password_hash")
    # exactly.
    password = models.CharField(max_length=128, db_column="password_hash", verbose_name="password")

    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=32, unique=True, null=True, blank=True)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.UNVERIFIED,
    )

    # Django admin-site access control only — distinct from the platform
    # `role` field above, which drives application-level RBAC (Phase 6 §6).
    # Not part of Phase 8 §4.1; required by Django's admin gating.
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(fields=["phone"], name="idx_users_phone"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    role__in=[
                        Role.STUDENT,
                        Role.INSTRUCTOR,
                        Role.ORGANIZATION,
                        Role.ADMIN,
                    ]
                ),
                name="ck_users_role",
            ),
            models.CheckConstraint(
                check=models.Q(
                    account_status__in=[
                        AccountStatus.UNVERIFIED,
                        AccountStatus.ACTIVE,
                        AccountStatus.SUSPENDED,
                    ]
                ),
                name="ck_users_account_status",
            ),
        ]

    def __str__(self):
        return self.email or self.phone or str(self.id)

    def clean(self):
        super().clean()
        if not self.email and not self.phone:
            raise ValidationError("A user must have at least an email or a phone number.")

    @property
    def is_active(self):
        return self.account_status == AccountStatus.ACTIVE

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.VERIFIED

    def has_perm(self, perm, obj=None):
        return self.role == Role.ADMIN

    def has_module_perms(self, app_label):
        return self.role == Role.ADMIN


class RefreshToken(models.Model):
    """
    CONFIRMED — Phase 8 §4.1 `refresh_tokens` table, verbatim.
    Stores only the SHA-256 hash of the raw refresh token — the raw value
    is never persisted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)

    class Meta:
        db_table = "refresh_tokens"
        indexes = [
            models.Index(fields=["user"], name="idx_refresh_user"),
        ]

    def __str__(self):
        return f"RefreshToken({self.id}) user={self.user_id} revoked={self.revoked}"

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self):
        return not self.revoked and not self.is_expired()


class VerificationCode(models.Model):
    """
    APPROVED — OWNER DECISION G1: minimal schema addition required to
    implement already-approved verification behavior. Phase 1
    FR-AUTH-001 and Phase 2 FLOW-AUTH-01 require verification-code
    expiry and failed-attempt handling; Phase 7 §4.1 requires the
    `VERIFICATION_CODE_EXPIRED` error case. Phase 8 §2/§4.1 does not
    enumerate a persistence mechanism for this already-approved
    behavior, so this table is the minimal addition needed to satisfy
    it. Scope is intentionally limited to registration verification
    only — not extended to password reset, MFA, or any other purpose.
    Stores only a hash of the code, mirroring RefreshToken's hashing
    policy; the raw code is never persisted.
    """

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_codes")
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.REGISTRATION)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "verification_codes"
        indexes = [
            models.Index(fields=["user", "purpose"], name="idx_verifcode_user_purpose"),
        ]

    def __str__(self):
        return f"VerificationCode(user={self.user_id}, purpose={self.purpose})"

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_consumed(self):
        return self.consumed_at is not None

    def is_usable(self, max_attempts):
        return not self.is_consumed() and not self.is_expired() and self.attempts < max_attempts