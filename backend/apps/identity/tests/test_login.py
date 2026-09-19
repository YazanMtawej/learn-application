from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import AccountStatus, User, VerificationStatus


class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("identity:login")
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(email="login@example.com", password=self.password)
        self.user.verification_status = VerificationStatus.VERIFIED
        self.user.account_status = AccountStatus.ACTIVE
        self.user.save(update_fields=["verification_status", "account_status"])

    def test_successful_login_with_email(self):
        response = self.client.post(
            self.url, {"identifier": "login@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data["data"])
        self.assertIn("refresh_token", response.data["data"])

    def test_successful_login_with_phone(self):
        User.objects.create_user(phone="+15551234567", password=self.password)
        User.objects.filter(phone="+15551234567").update(
            verification_status=VerificationStatus.VERIFIED,
            account_status=AccountStatus.ACTIVE,
        )
        response = self.client.post(
            self.url, {"identifier": "+15551234567", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_wrong_password_returns_generic_invalid_credentials(self):
        response = self.client.post(
            self.url, {"identifier": "login@example.com", "password": "WrongPassword1!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")

    def test_nonexistent_identifier_returns_generic_invalid_credentials(self):
        response = self.client.post(
            self.url, {"identifier": "nobody@example.com", "password": "WhatEver123!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")

    def test_unverified_account_cannot_login(self):
        User.objects.create_user(email="pending@example.com", password=self.password)
        response = self.client.post(
            self.url, {"identifier": "pending@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")

    def test_suspended_account_returns_distinct_error(self):
        self.user.account_status = AccountStatus.SUSPENDED
        self.user.save(update_fields=["account_status"])
        response = self.client.post(
            self.url, {"identifier": "login@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "ACCOUNT_SUSPENDED")

    def test_login_response_does_not_expose_password_hash(self):
        response = self.client.post(
            self.url, {"identifier": "login@example.com", "password": self.password}, format="json"
        )
        self.assertNotIn("password", response.data["data"]["user"])