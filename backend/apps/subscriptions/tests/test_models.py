import uuid

from django.db import IntegrityError
from django.test import TestCase

from apps.identity.models import User
from apps.subscriptions.models import Entitlement, PaymentEvent, Plan, Subscription


class PlanModelTests(TestCase):
    def test_plan_code_uniqueness_enforced(self):
        Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro")
        with self.assertRaises(IntegrityError):
            Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro Duplicate")

    def test_plan_invalid_code_rejected_by_constraint(self):
        plan = Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro")
        plan.code = "not_a_real_plan"
        with self.assertRaises(IntegrityError):
            plan.save()


class EntitlementModelTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro")

    def test_unique_feature_key_per_plan_enforced(self):
        Entitlement.objects.create(plan=self.plan, feature_key="ai_hints_per_day", limit_value=50)
        with self.assertRaises(IntegrityError):
            Entitlement.objects.create(plan=self.plan, feature_key="ai_hints_per_day", limit_value=100)

    def test_limit_value_optional(self):
        entitlement = Entitlement.objects.create(plan=self.plan, feature_key="unlimited_feature")
        self.assertIsNone(entitlement.limit_value)


class SubscriptionModelTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro")
        self.user = User.objects.create_user(email="subuser@example.com", password="StrongPass123!")

    def test_subscription_status_choices_enforced_by_constraint(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan, status="active")
        sub.status = "not_a_real_status"
        with self.assertRaises(IntegrityError):
            sub.save()

    def test_multiple_subscriptions_per_user_allowed(self):
        Subscription.objects.create(user=self.user, plan=self.plan, status="cancelled")
        Subscription.objects.create(user=self.user, plan=self.plan, status="active")
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 2)

    def test_cascade_delete_on_user_removes_subscriptions(self):
        Subscription.objects.create(user=self.user, plan=self.plan, status="active")
        self.user.delete()
        self.assertEqual(Subscription.objects.count(), 0)


class PaymentEventModelTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(id=uuid.uuid4(), code="pro", name="Pro")
        self.user = User.objects.create_user(email="payuser@example.com", password="StrongPass123!")
        self.subscription = Subscription.objects.create(user=self.user, plan=self.plan, status="active")

    def test_provider_event_id_uniqueness_enforced(self):
        from django.utils import timezone

        PaymentEvent.objects.create(
            subscription=self.subscription,
            provider_event_id="evt_123",
            type="payment_succeeded",
            payload_ref="{}",
            processed_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            PaymentEvent.objects.create(
                subscription=self.subscription,
                provider_event_id="evt_123",
                type="payment_failed",
                payload_ref="{}",
                processed_at=timezone.now(),
            )