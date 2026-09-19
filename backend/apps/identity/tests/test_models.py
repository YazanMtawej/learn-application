import uuid
from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.identity.models import (
    AccountStatus,
    RefreshToken,
    Role,
    User,
    VerificationCode,
    VerificationStatus,
)


class UserModelTests(TestCase):
    def test_user_has_uuid_primary_key(self):
        user = User.objects.create_user(email="alice@example.com", password="StrongPass123!")
        self.assertIsInstance(user.id, uuid.UUID)

    def test_default_role_is_student(self):
        user = User.objects.create_user(email="bob@example.com", password="StrongPass123!")
        self.assertEqual(user.role, Role.STUDENT)

    def test_default_verification_and_account_status(self):
        user = User.objects.create_user(email="carol@example.com", password="StrongPass123!")
        self.assertEqual(user.verification_status, VerificationStatus.UNVERIFIED)
        self.assertEqual(user.account_status, AccountStatus.UNVERIFIED)

    def test_password_is_hashed_not_plaintext(self):
        user = User.objects.create_user(email="dave@example.com", password="StrongPass123!")
        self.assertNotEqual(user.password, "StrongPass123!")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertFalse(user.check_password("WrongPassword"))

    def test_email_uniqueness_enforced(self):
        User.objects.create_user(email="dup@example.com", password="StrongPass123!")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com", password="AnotherPass123!")

    def test_phone_uniqueness_enforced(self):
        User.objects.create_user(phone="+10000000001", password="StrongPass123!")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(phone="+10000000001", password="AnotherPass123!")

    def test_multiple_users_can_have_null_email(self):
        User.objects.create_user(phone="+10000000002", password="StrongPass123!")
        User.objects.create_user(phone="+10000000003", password="StrongPass123!")

    def test_user_without_identifier_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(password="StrongPass123!")

    def test_role_choices_restricted_by_check_constraint(self):
        user = User.objects.create_user(email="eve@example.com", password="StrongPass123!")
        user.role = "not_a_real_role"
        with self.assertRaises(IntegrityError):
            user.save()

    def test_is_active_property_reflects_account_status(self):
        user = User.objects.create_user(email="frank@example.com", password="StrongPass123!")
        self.assertFalse(user.is_active)
        user.account_status = AccountStatus.ACTIVE
        user.save(update_fields=["account_status"])
        self.assertTrue(user.is_active)


class RefreshTokenModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="grace@example.com", password="StrongPass123!")

    def test_refresh_token_created_with_expected_fields(self):
        token = RefreshToken.objects.create(
            user=self.user,
            token_hash="a" * 64,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.assertFalse(token.revoked)
        self.assertIsInstance(token.id, uuid.UUID)

    def test_token_hash_uniqueness_enforced(self):
        RefreshToken.objects.create(
            user=self.user, token_hash="b" * 64, expires_at=timezone.now() + timedelta(days=1)
        )
        with self.assertRaises(IntegrityError):
            RefreshToken.objects.create(
                user=self.user, token_hash="b" * 64, expires_at=timezone.now() + timedelta(days=1)
            )

    def test_is_expired_true_for_past_expiry(self):
        token = RefreshToken.objects.create(
            user=self.user,
            token_hash="c" * 64,
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(token.is_expired())
        self.assertFalse(token.is_valid())

    def test_is_valid_false_when_revoked(self):
        token = RefreshToken.objects.create(
            user=self.user,
            token_hash="d" * 64,
            expires_at=timezone.now() + timedelta(days=1),
            revoked=True,
        )
        self.assertFalse(token.is_valid())

    def test_cascade_delete_removes_tokens(self):
        RefreshToken.objects.create(
            user=self.user, token_hash="e" * 64, expires_at=timezone.now() + timedelta(days=1)
        )
        self.user.delete()
        self.assertEqual(RefreshToken.objects.count(), 0)


class VerificationCodeModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="heidi@example.com", password="StrongPass123!")

    def test_verification_code_defaults(self):
        code = VerificationCode.objects.create(
            user=self.user,
            code_hash="f" * 64,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.assertEqual(code.purpose, VerificationCode.Purpose.REGISTRATION)
        self.assertEqual(code.attempts, 0)
        self.assertIsNone(code.consumed_at)

    def test_is_usable_false_when_expired(self):
        code = VerificationCode.objects.create(
            user=self.user,
            code_hash="g" * 64,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(code.is_usable(max_attempts=5))

    def test_is_usable_false_when_consumed(self):
        code = VerificationCode.objects.create(
            user=self.user,
            code_hash="h" * 64,
            expires_at=timezone.now() + timedelta(minutes=15),
            consumed_at=timezone.now(),
        )
        self.assertFalse(code.is_usable(max_attempts=5))

    def test_is_usable_false_when_attempts_exhausted(self):
        code = VerificationCode.objects.create(
            user=self.user,
            code_hash="i" * 64,
            expires_at=timezone.now() + timedelta(minutes=15),
            attempts=5,
        )
        self.assertFalse(code.is_usable(max_attempts=5))