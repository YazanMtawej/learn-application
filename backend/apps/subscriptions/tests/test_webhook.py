import hashlib
import hmac
import json
from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.subscriptions.models import PaymentEvent, Plan, Subscription

WEBHOOK_SECRET = "test-webhook-secret"


def _signed_post(client, url, payload: dict, secret: str = WEBHOOK_SECRET):
    raw_body = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    return client.post(
        url, data=raw_body, content_type="application/json", HTTP_X_WEBHOOK_SIGNATURE=signature
    )


@override_settings(PAYMENT_WEBHOOK_SECRET=WEBHOOK_SECRET)
class PaymentWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("payment_webhook")
        self.plan = Plan.objects.get(code="pro")
        self.user = User.objects.create_user(email="webhookuser@example.com", password="StrongPass123!")
        self.subscription = Subscription.objects.create(
            user=self.user, plan=self.plan, status=Subscription.Status.ACTIVE
        )

    def test_invalid_signature_rejected(self):
        response = _signed_post(
            self.client,
            self.url,
            {
                "provider_event_id": "evt_1",
                "type": "payment_failed",
                "subscription_id": str(self.subscription.id),
            },
            secret="wrong-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "INVALID_WEBHOOK_SIGNATURE")

    def test_missing_signature_header_rejected(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"provider_event_id": "evt_2", "type": "payment_failed"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_failed_transitions_active_subscription_to_grace(self):
        response = _signed_post(
            self.client,
            self.url,
            {
                "provider_event_id": "evt_failed_1",
                "type": "payment_failed",
                "subscription_id": str(self.subscription.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["ack"])

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.GRACE)
        self.assertIsNotNone(self.subscription.grace_period_end)

        expected_end = timezone.now() + timedelta(days=settings.SUBSCRIPTION_GRACE_PERIOD_DAYS)
        delta = abs((self.subscription.grace_period_end - expected_end).total_seconds())
        self.assertLess(delta, 5)

    def test_payment_succeeded_restores_grace_subscription_to_active(self):
        self.subscription.status = Subscription.Status.GRACE
        self.subscription.grace_period_end = timezone.now() + timedelta(days=3)
        self.subscription.save(update_fields=["status", "grace_period_end"])

        response = _signed_post(
            self.client,
            self.url,
            {
                "provider_event_id": "evt_success_1",
                "type": "payment_succeeded",
                "subscription_id": str(self.subscription.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertIsNone(self.subscription.grace_period_end)

    def test_duplicate_event_is_idempotent(self):
        payload = {
            "provider_event_id": "evt_dup_1",
            "type": "payment_failed",
            "subscription_id": str(self.subscription.id),
        }
        first_response = _signed_post(self.client, self.url, payload)
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        self.subscription.refresh_from_db()
        first_grace_end = self.subscription.grace_period_end

        second_response = _signed_post(self.client, self.url, payload)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(second_response.data["data"]["ack"])

        self.assertEqual(PaymentEvent.objects.filter(provider_event_id="evt_dup_1").count(), 1)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.grace_period_end, first_grace_end)

    def test_unknown_subscription_id_rejected(self):
        response = _signed_post(
            self.client,
            self.url,
            {
                "provider_event_id": "evt_unknown_sub",
                "type": "payment_failed",
                "subscription_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "WEBHOOK_SUBSCRIPTION_NOT_FOUND")

    def test_missing_required_field_rejected(self):
        response = _signed_post(self.client, self.url, {"type": "payment_failed"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "WEBHOOK_PAYLOAD_INVALID")