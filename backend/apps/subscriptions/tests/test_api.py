from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.subscriptions.models import Plan, Subscription


def _active_authenticated_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


class PlansListTests(TestCase):
    def setUp(self):
        self.url = reverse("subscriptions:plans")
        self.client, self.user = _active_authenticated_client("plansuser@example.com")

    def test_seeded_plans_are_returned(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {p["code"] for p in response.data["data"]["plans"]}
        self.assertEqual(codes, {"free", "pro", "student", "organization"})

    def test_no_price_field_exposed(self):
        response = self.client.get(self.url)
        for plan in response.data["data"]["plans"]:
            self.assertNotIn("price", plan)

    def test_unauthenticated_access_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SubscriptionStateTests(TestCase):
    def setUp(self):
        self.url = reverse("subscriptions:state")
        self.client, self.user = _active_authenticated_client("stateuser@example.com")

    def test_state_defaults_to_free_with_no_subscription(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "free")
        self.assertEqual(response.data["data"]["plan"], "free")
        self.assertIsNone(response.data["data"]["grace_period_end"])

    def test_state_reflects_active_subscription(self):
        pro_plan = Plan.objects.get(code="pro")
        Subscription.objects.create(user=self.user, plan=pro_plan, status=Subscription.Status.ACTIVE)
        response = self.client.get(self.url)
        self.assertEqual(response.data["data"]["status"], "active")
        self.assertEqual(response.data["data"]["plan"], "pro")


class SubscriptionUpgradeTests(TestCase):
    def setUp(self):
        self.url = reverse("subscriptions:upgrade")
        self.client, self.user = _active_authenticated_client("upgradeuser@example.com")

    def test_upgrade_creates_active_subscription(self):
        pro_plan = Plan.objects.get(code="pro")
        response = self.client.post(
            self.url,
            {"plan_id": str(pro_plan.id), "payment_method_ref": "pm_ref_123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["subscription_status"], "active")
        self.assertTrue(
            Subscription.objects.filter(
                user=self.user, plan=pro_plan, status=Subscription.Status.ACTIVE
            ).exists()
        )

    def test_upgrade_with_invalid_plan_id_returns_not_found(self):
        response = self.client.post(
            self.url,
            {"plan_id": "00000000-0000-0000-0000-000000000000", "payment_method_ref": "pm_ref"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "PLAN_NOT_FOUND")

    def test_upgrade_does_not_persist_payment_method_ref(self):
        pro_plan = Plan.objects.get(code="pro")
        self.client.post(
            self.url,
            {"plan_id": str(pro_plan.id), "payment_method_ref": "pm_super_secret"},
            format="json",
        )
        subscription = Subscription.objects.get(user=self.user)
        for field in subscription._meta.get_fields():
            self.assertNotEqual(field.name, "payment_method_ref")

    def test_upgrade_isolated_between_users(self):
        other_client, other_user = _active_authenticated_client("otheruser@example.com")
        pro_plan = Plan.objects.get(code="pro")
        self.client.post(
            self.url, {"plan_id": str(pro_plan.id), "payment_method_ref": "pm_ref"}, format="json"
        )
        self.assertFalse(Subscription.objects.filter(user=other_user).exists())


class SubscriptionCancelTests(TestCase):
    def setUp(self):
        self.upgrade_url = reverse("subscriptions:upgrade")
        self.cancel_url = reverse("subscriptions:cancel")
        self.client, self.user = _active_authenticated_client("canceluser@example.com")

    def test_cancel_with_no_subscription_returns_not_found(self):
        response = self.client.post(self.cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "SUBSCRIPTION_NOT_FOUND")

    def test_successful_cancellation(self):
        pro_plan = Plan.objects.get(code="pro")
        self.client.post(
            self.upgrade_url, {"plan_id": str(pro_plan.id), "payment_method_ref": "pm"}, format="json"
        )
        response = self.client.post(self.cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["effective_end_date"])

        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.status, Subscription.Status.CANCELLED)

    def test_cancel_already_cancelled_returns_conflict(self):
        pro_plan = Plan.objects.get(code="pro")
        self.client.post(
            self.upgrade_url, {"plan_id": str(pro_plan.id), "payment_method_ref": "pm"}, format="json"
        )
        self.client.post(self.cancel_url, {}, format="json")
        response = self.client.post(self.cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "SUBSCRIPTION_NOT_CANCELLABLE")