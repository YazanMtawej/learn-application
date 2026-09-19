from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import AccountStatus, RefreshToken, User, VerificationStatus
from apps.identity.services import AuthService


class RefreshTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.refresh_url = reverse("identity:refresh")
        self.login_url = reverse("identity:login")
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(email="refresh@example.com", password=self.password)
        self.user.verification_status = VerificationStatus.VERIFIED
        self.user.account_status = AccountStatus.ACTIVE
        self.user.save(update_fields=["verification_status", "account_status"])

        login_response = self.client.post(
            self.login_url, {"identifier": "refresh@example.com", "password": self.password}, format="json"
        )
        self.initial_refresh_token = login_response.data["data"]["refresh_token"]

    def test_refresh_returns_new_token_pair(self):
        response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data["data"])
        self.assertIn("refresh_token", response.data["data"])
        self.assertNotEqual(response.data["data"]["refresh_token"], self.initial_refresh_token)

    def test_old_refresh_token_is_revoked_after_rotation(self):
        first_response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        replay_response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(replay_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(replay_response.data["error"]["code"], "REFRESH_TOKEN_REVOKED")

    def test_new_refresh_token_from_rotation_is_valid(self):
        first_response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        new_refresh_token = first_response.data["data"]["refresh_token"]

        second_response = self.client.post(
            self.refresh_url, {"refresh_token": new_refresh_token}, format="json"
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

    def test_expired_refresh_token_rejected(self):
        stored = RefreshToken.objects.get(user=self.user)
        stored.expires_at = timezone.now() - timedelta(days=1)
        stored.save(update_fields=["expires_at"])

        response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "REFRESH_TOKEN_EXPIRED")

    def test_invalid_refresh_token_rejected(self):
        response = self.client.post(
            self.refresh_url, {"refresh_token": "not-a-real-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "REFRESH_TOKEN_INVALID")

    def test_revoked_refresh_token_rejected(self):
        AuthService.revoke_refresh_token(self.initial_refresh_token, user=self.user)
        response = self.client.post(
            self.refresh_url, {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "REFRESH_TOKEN_REVOKED")

    def test_logout_revokes_refresh_token(self):
        login_response = self.client.post(
            self.login_url, {"identifier": "refresh@example.com", "password": self.password}, format="json"
        )
        access_token = login_response.data["data"]["access_token"]
        refresh_token = login_response.data["data"]["refresh_token"]

        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        logout_response = authed_client.post(
            reverse("identity:logout"), {"refresh_token": refresh_token}, format="json"
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        replay_response = self.client.post(
            self.refresh_url, {"refresh_token": refresh_token}, format="json"
        )
        self.assertEqual(replay_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        response = self.client.post(
            reverse("identity:logout"), {"refresh_token": self.initial_refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)