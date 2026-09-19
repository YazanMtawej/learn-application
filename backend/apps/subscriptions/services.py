import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.subscriptions.exceptions import (
    PlanNotFoundError,
    SubscriptionNotCancellableError,
    SubscriptionNotFoundError,
    WebhookPayloadInvalidError,
    WebhookSubscriptionNotFoundError,
)
from apps.subscriptions.models import Entitlement, PaymentEvent, Plan, Subscription


class SubscriptionService:
    """Application-layer subscription/entitlement logic (Phase 6 §5, Phase 4 §12)."""

    @staticmethod
    def get_current_subscription(user):
        return Subscription.objects.filter(user=user).order_by("-created_at").first()

    @staticmethod
    def get_effective_plan(user) -> Plan:
        """
        Deterministic entitlement resolution (Phase 4 §15 Invariant:
        "Subscription Entitlement ≠ Role" — resolved here purely from
        subscription state, never from client input). A subscription in
        {trial, active, grace} grants its plan; anything else (no
        subscription row, past_due, expired, cancelled) falls back to
        the Free plan — matching Phase 1 §16 "Expiration: العودة تلقائية
        لحدود خطة Free" without requiring an unsupported 'free' status
        enum value (Phase 8 §4.10 does not include 'free' in the status
        CHECK constraint).
        """
        current = SubscriptionService.get_current_subscription(user)
        if current and current.status in Subscription.ENTITLED_STATUSES:
            return current.plan
        return Plan.objects.get(code=Plan.Code.FREE)

    @staticmethod
    def has_entitlement(user, feature_key: str):
        plan = SubscriptionService.get_effective_plan(user)
        return Entitlement.objects.filter(plan=plan, feature_key=feature_key).first()

    @classmethod
    @transaction.atomic
    def upgrade(cls, user, plan_id, payment_method_ref: str) -> Subscription:
        """
        Phase 1 §16: "Upgrade: فوري، تفعيل الميزات فورًا". Real payment
        processing is out of scope (Phase 1 §1.2); `payment_method_ref`
        is accepted per the Phase 7 §4.9 request contract but is not
        persisted — no column exists for it on `subscriptions`
        (Phase 8 §4.10), and storing raw payment references outside the
        payment provider is a Phase 1 §23 privacy/security concern this
        MVP does not need to take on.
        """
        del payment_method_ref  # accepted for contract compliance; not persisted (see docstring)

        try:
            plan = Plan.objects.get(id=plan_id)
        except (Plan.DoesNotExist, ValueError, TypeError):
            raise PlanNotFoundError()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
        return subscription

    @classmethod
    @transaction.atomic
    def cancel(cls, user) -> Subscription:
        """
        Phase 1 §16: "Cancellation: يبقى الوصول حتى نهاية الفترة المدفوعة".
        `current_period_end` may be null (no billing-cycle length is
        documented anywhere in Phase 0-17) — `effective_end_date` is
        returned honestly as null in that case rather than fabricating a
        duration.
        """
        current = cls.get_current_subscription(user)
        if current is None:
            raise SubscriptionNotFoundError()
        if current.status not in Subscription.CANCELLABLE_STATUSES:
            raise SubscriptionNotCancellableError()

        current.status = Subscription.Status.CANCELLED
        current.save(update_fields=["status", "updated_at"])
        return current

    @classmethod
    @transaction.atomic
    def process_webhook(cls, payload: dict) -> PaymentEvent:
        """
        Phase 7 §4.9 SUB-WEBHOOK. Idempotency via
        `payment_events.provider_event_id UNIQUE` (Phase 8 §4.10) — a
        repeated provider_event_id is acknowledged as a no-op rather
        than treated as an error, matching "Payment Providers تعيد إرسال
        نفس الحدث" (Phase 7 §12).

        No specific payment provider is integrated (Phase 1 §1.2), so
        the payload shape consumed here — provider_event_id, type,
        subscription_id, optional current_period_end — is this
        project's own minimal, documented resolution to Phase 7's
        loosely-specified "provider payload", not a vendor contract.
        """
        provider_event_id = payload.get("provider_event_id")
        event_type = payload.get("type")
        subscription_id = payload.get("subscription_id")

        if not provider_event_id or not event_type or not subscription_id:
            raise WebhookPayloadInvalidError()

        existing = PaymentEvent.objects.filter(provider_event_id=provider_event_id).first()
        if existing is not None:
            return existing

        try:
            subscription = Subscription.objects.select_for_update().get(id=subscription_id)
        except (Subscription.DoesNotExist, ValueError, TypeError):
            raise WebhookSubscriptionNotFoundError()

        event = PaymentEvent.objects.create(
            subscription=subscription,
            provider_event_id=provider_event_id,
            type=event_type,
            payload_ref=json.dumps(payload),
            processed_at=timezone.now(),
        )

        if event_type == "payment_failed":
            cls._handle_payment_failed(subscription)
        elif event_type == "payment_succeeded":
            cls._handle_payment_succeeded(subscription, payload)

        return event

    @staticmethod
    def _handle_payment_failed(subscription: Subscription) -> None:
        """
        Phase 2 FLOW-SUB-02: "فشل → Grace Period (7 أيام ثابتة، لا قطع
        فوري)". The FLOW narrative moves directly from failure into the
        Grace Period without a separate observable step, so this
        transitions {trial, active} directly to 'grace' rather than
        routing through 'past_due' first — Phase 2 SM-02 lists 'past_due'
        as a distinct state, but no documented trigger rule specifies
        when a webhook event should land there instead of 'grace'. This
        is flagged as a non-blocking documentation gap; 'past_due'
        remains a valid, cancellable status but is not auto-entered by
        this webhook logic.
        """
        if subscription.status in (Subscription.Status.TRIAL, Subscription.Status.ACTIVE):
            subscription.status = Subscription.Status.GRACE
            subscription.grace_period_end = timezone.now() + timedelta(
                days=settings.SUBSCRIPTION_GRACE_PERIOD_DAYS
            )
            subscription.save(update_fields=["status", "grace_period_end", "updated_at"])

    @staticmethod
    def _handle_payment_succeeded(subscription: Subscription, payload: dict) -> None:
        """
        Phase 2 FLOW-SUB-02: "نجاح خلال الـ7 أيام → استعادة Active فورًا
        (بدون فقدان Mastery/Progress)" — Mastery/Progress preservation is
        inherent here since this service only ever mutates
        `subscriptions` fields, never touches any other bounded
        context's data (Phase 4 §14 Domain Ownership).
        """
        if subscription.status in (Subscription.Status.GRACE, Subscription.Status.PAST_DUE):
            subscription.status = Subscription.Status.ACTIVE
            subscription.grace_period_end = None

            raw_period_end = payload.get("current_period_end")
            if raw_period_end:
                parsed = parse_datetime(raw_period_end)
                if parsed is not None:
                    subscription.current_period_end = parsed

            subscription.save(
                update_fields=["status", "grace_period_end", "current_period_end", "updated_at"]
            )

    @classmethod
    def expire_overdue_grace_subscriptions(cls) -> int:
        """
        Phase 1 §16: "بعد 7 أيام بدون نجاح → Past Due/Expired → Apply
        Entitlement Rules". This is a deterministic, callable,
        time-based transition — not wired to a Celery beat schedule in
        this task (scheduling/orchestration is deferred; see final
        review). `get_effective_plan` already falls back to Free for any
        non-{trial,active,grace} subscription, so no further mutation is
        needed once a subscription is marked 'expired'.
        """
        now = timezone.now()
        overdue = Subscription.objects.filter(
            status=Subscription.Status.GRACE, grace_period_end__lt=now
        )
        return overdue.update(status=Subscription.Status.EXPIRED)