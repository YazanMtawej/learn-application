from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.identity.models import User
from apps.subscriptions.models import Plan, Subscription
from apps.subscriptions.services import SubscriptionService


class GraceExpirationTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.get(code="pro")
        self.free_plan = Plan.objects.get(code="free")
        self.user = User.objects.create_user(email="graceuser@example.com", password="StrongPass123!")

    def test_overdue_grace_subscription_is_expired(self):
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.GRACE,
            grace_period_end=timezone.now() - timedelta(days=1),
        )
        expired_count = SubscriptionService.expire_overdue_grace_subscriptions()
        self.assertEqual(expired_count, 1)

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.EXPIRED)

    def test_grace_subscription_not_yet_overdue_is_untouched(self):
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.GRACE,
            grace_period_end=timezone.now() + timedelta(days=2),
        )
        expired_count = SubscriptionService.expire_overdue_grace_subscriptions()
        self.assertEqual(expired_count, 0)

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.GRACE)

    def test_effective_plan_falls_back_to_free_after_expiration(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.GRACE,
            grace_period_end=timezone.now() - timedelta(days=1),
        )
        SubscriptionService.expire_overdue_grace_subscriptions()

        effective_plan = SubscriptionService.get_effective_plan(self.user)
        self.assertEqual(effective_plan.code, Plan.Code.FREE)