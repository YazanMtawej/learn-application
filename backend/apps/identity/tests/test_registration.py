from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import User, VerificationCode, VerificationStatus
from apps.identity.services import AuthService


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("identity:register")

    def test_successful_registration_with_email_identifier(self):
        response = self.client.post(
            self.url,
            {"identifier": "newuser@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user_id", response.data["data"])
        self.assertEqual(response.data["data"]["verification_state"], VerificationStatus.UNVERIFIED)

        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.verification_status, VerificationStatus.UNVERIFIED)
        self.assertEqual(user.account_status, "unverified")
        self.assertIsNone(user.phone)

    def test_successful_registration_with_phone_identifier(self):
        response = self.client.post(
            self.url,
            {"identifier": "+15550001111", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(phone="+15550001111")
        self.assertIsNone(user.email)

    def test_registration_requires_identifier_field(self):
        response = self.client.post(self.url, {"password": "StrongPass123!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["category"], "validation")

    def test_registration_requires_password_field(self):
        response = self.client.post(self.url, {"identifier": "nopass@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_email_identifier_returns_identifier_taken(self):
        User.objects.create_user(email="dup@example.com", password="StrongPass123!")
        response = self.client.post(
            self.url,
            {"identifier": "dup@example.com", "password": "AnotherPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "IDENTIFIER_TAKEN")

    def test_duplicate_phone_identifier_returns_identifier_taken(self):
        User.objects.create_user(phone="+15550002222", password="StrongPass123!")
        response = self.client.post(
            self.url,
            {"identifier": "+15550002222", "password": "AnotherPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "IDENTIFIER_TAKEN")

    def test_weak_password_rejected(self):
        response = self.client.post(
            self.url,
            {"identifier": "weakpass@example.com", "password": "12345"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_is_hashed_after_registration(self):
        self.client.post(
            self.url,
            {"identifier": "hashed@example.com", "password": "StrongPass123!"},
            format="json",
        )
        user = User.objects.get(email="hashed@example.com")
        self.assertNotEqual(user.password, "StrongPass123!")

    def test_non_email_like_identifier_is_treated_as_phone(self):
        """
        Documents the accepted detection heuristic (OWNER DECISION G3):
        anything that does not validate as an email is treated as a
        phone number, with no phone-format validation performed
        (consistent with Phase 8's unconstrained `phone` column).
        """
        response = self.client.post(
            self.url,
            {"identifier": "not-an-email-string", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(phone="not-an-email-string").exists())

    def test_verification_code_is_not_written_to_response(self):
        response = self.client.post(
            self.url,
            {"identifier": "nocode@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertNotIn("code", response.data["data"])


class VerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.verify_url = reverse("identity:verify")
        self.user, self.raw_code = AuthService.register(
            email="verifyme@example.com", phone=None, password="StrongPass123!"
        )

    def test_successful_verification_activates_account(self):
        response = self.client.post(
            self.verify_url,
            {"user_id": str(self.user.id), "code": self.raw_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["verified"])

        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_status, "verified")
        self.assertEqual(self.user.account_status, "active")

    def test_invalid_code_rejected(self):
        response = self.client.post(
            self.verify_url,
            {"user_id": str(self.user.id), "code": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VERIFICATION_CODE_INVALID")

    def test_expired_code_rejected(self):
        VerificationCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.post(
            self.verify_url,
            {"user_id": str(self.user.id), "code": self.raw_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VERIFICATION_CODE_EXPIRED")

    def test_already_verified_rejected(self):
        self.client.post(
            self.verify_url, {"user_id": str(self.user.id), "code": self.raw_code}, format="json"
        )
        response = self.client.post(
            self.verify_url, {"user_id": str(self.user.id), "code": self.raw_code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "ALREADY_VERIFIED")

    def test_unknown_user_id_rejected(self):
        response = self.client.post(
            self.verify_url,
            {"user_id": "00000000-0000-0000-0000-000000000000", "code": "123456"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_max_verification_attempts_exceeded_rejects_further_attempts(self):
        from django.conf import settings

        max_attempts = settings.VERIFICATION_MAX_ATTEMPTS

        for _ in range(max_attempts):
            response = self.client.post(
                self.verify_url,
                {"user_id": str(self.user.id), "code": "000000"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["error"]["code"], "VERIFICATION_CODE_INVALID")

        # Attempts are now exhausted — even the correct code must be rejected.
        final_response = self.client.post(
            self.verify_url,
            {"user_id": str(self.user.id), "code": self.raw_code},
            format="json",
        )
        self.assertEqual(final_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(final_response.data["error"]["code"], "VERIFICATION_CODE_INVALID")

        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_status, VerificationStatus.UNVERIFIED)