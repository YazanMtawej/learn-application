import uuid

from django.conf import settings
from django.db import models


class Plan(models.Model):
    """
    CONFIRMED — Phase 8 §4.10 `plans` table.

    No price column exists (D5: no pricing in V1).
    Seeded via migration 0002 with the four codes documented
    in Phase 1 §16 / Phase 8 §4.10 CHECK constraint.
    """

    class Code(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        STUDENT = "student", "Student"
        ORGANIZATION = "organization", "Organization"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    code = models.CharField(
        max_length=20,
        choices=Code.choices,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    class Meta:
        db_table = "plans"

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    code__in=[
                        "free",
                        "pro",
                        "student",
                        "organization",
                    ]
                ),
                name="ck_plans_code",
            ),
        ]

    def __str__(self):
        return self.code


class Entitlement(models.Model):
    """
    CONFIRMED — Phase 8 §4.10 `entitlements` table.

    `feature_key` / `limit_value` are read/write primitives only;
    no rows are seeded here since exact entitlement numbers are TBD
    across Phase 1 §16, Phase 3 §16, and Phase 10 P10-D15.

    Inventing values would violate the "no invented numbers" rule.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="entitlements",
    )

    feature_key = models.CharField(
        max_length=100,
    )

    limit_value = models.IntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "entitlements"

        indexes = [
            models.Index(
                fields=["plan"],
                name="idx_ent_plan",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["plan", "feature_key"],
                name="uq_entitlements_plan_feature",
            ),
        ]

    def __str__(self):
        return f"{self.plan.code}:{self.feature_key}"


class Subscription(models.Model):
    """
    CONFIRMED core fields — Phase 8 §4.10 `subscriptions` table
    (user_id, plan_id, status, current_period_end, grace_period_end).

    Phase 8 §4.10 CHECK status enum, Phase 2 SM-02 state machine.

    `user` FK is intentionally NOT unique: Phase 8 §4.10 lists a
    UNIQUE constraint explicitly for `plans`, `entitlements`, and
    `payment_events`, but not for `subscriptions.user_id`.

    This is read as deliberate, allowing a user to accumulate multiple
    subscription rows over time (re-subscription after
    cancellation/expiration creates a new row rather than mutating
    an old one).

    "Current subscription" = latest row by created_at.

    created_at/updated_at are NOT in the original Phase 8 schema;
    they follow the same non-blocking, low-risk addition pattern used
    in Task 1 for `User`, and are needed to order "current subscription"
    deterministically.
    """

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        GRACE = "grace", "Grace"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    CANCELLABLE_STATUSES = (
        Status.TRIAL,
        Status.ACTIVE,
        Status.PAST_DUE,
        Status.GRACE,
    )

    ENTITLED_STATUSES = (
        Status.TRIAL,
        Status.ACTIVE,
        Status.GRACE,
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    grace_period_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "subscriptions"

        indexes = [
            models.Index(
                fields=["user"],
                name="idx_sub_user",
            ),
            models.Index(
                fields=["status"],
                name="idx_sub_status",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    status__in=[
                        "trial",
                        "active",
                        "past_due",
                        "grace",
                        "expired",
                        "cancelled",
                    ]
                ),
                name="ck_subscriptions_status",
            ),
        ]

    def __str__(self):
        return (
            f"Subscription({self.id}) "
            f"user={self.user_id} "
            f"status={self.status}"
        )


class PaymentEvent(models.Model):
    """
    CONFIRMED — Phase 8 §4.10 `payment_events` table.

    `provider_event_id UNIQUE` enforces idempotency for SUB-WEBHOOK
    (Phase 7 §4.9: "Payment Providers تعيد إرسال نفس الحدث").
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="payment_events",
    )

    provider_event_id = models.CharField(
        max_length=255,
        unique=True,
    )

    type = models.CharField(
        max_length=50,
    )

    payload_ref = models.TextField()

    processed_at = models.DateTimeField()

    class Meta:
        db_table = "payment_events"

        indexes = [
            models.Index(
                fields=["subscription"],
                name="idx_pe_subscription",
            ),
        ]

    def __str__(self):
        return f"PaymentEvent({self.provider_event_id})"