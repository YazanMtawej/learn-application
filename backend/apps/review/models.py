import uuid

from django.conf import settings
from django.db import models


class ReviewSession(models.Model):
    """
    CONFIRMED — Phase 8 §4.8 `review_sessions` table, verbatim
    (id, user_id, trigger_context, status, created_at).

    `trigger_context` values are limited to the documented Trigger set
    (Phase 17 §6.A): module_completed (E1), assessment_remediation (E2),
    review_concept / review_prerequisite (E4). F1 (active_flaw) is
    deliberately excluded — Phase 17 §6 confirms it is a
    Content-Eligibility Filter, never a Trigger.

    Status transitions follow Phase 2 SM-04 exactly:
    Pending → Active → Completed / Remediation → (retry) Active.
    """

    class TriggerContext(models.TextChoices):
        MODULE_COMPLETED = "module_completed", "Module Completed"
        ASSESSMENT_REMEDIATION = "assessment_remediation", "Assessment Remediation"
        REVIEW_CONCEPT = "review_concept", "Review Concept"
        REVIEW_PREREQUISITE = "review_prerequisite", "Review Prerequisite"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        REMEDIATION = "remediation", "Remediation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="review_sessions"
    )
    trigger_context = models.CharField(max_length=30, choices=TriggerContext.choices)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_sessions"
        indexes = [
            models.Index(fields=["user"], name="idx_rs_user"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    status__in=["pending", "active", "completed", "remediation"]
                ),
                name="ck_review_sessions_status",
            ),
        ]

    def __str__(self):
        return f"ReviewSession({self.id}) user={self.user_id} status={self.status}"


class ReviewItem(models.Model):
    """
    CONFIRMED core fields — Phase 8 §4.8 `review_items` table
    (id, review_session_id, concept_id, question_ref, outcome).

    `question_ref`: ENGINEERING DECISION — implemented as an FK to
    `learning_content.Exercise` rather than a free-form reference,
    because no question-bank entity exists anywhere in the approved
    schema (Phase 17 §7 itself defers the bank's internal mechanics).

    `attempt`: NOT in Phase 8 §4.8. ENGINEERING DECISION — added as a
    nullable 1:1 link to `execution.ExerciseAttempt` so Review can reuse
    TASK 4's full Execution/Evaluation pipeline verbatim rather than
    duplicating deterministic evaluation logic (a higher-order project
    principle, Phase 0 §9). This is also how Evidence gets produced
    for review outcomes — see TASK 8 Final Report, Open Documentation
    Gap #1, for the explicit divergence this creates from Phase 15
    §6.2's "review_item" source_type naming.

    `outcome`: Phase 8 does not enumerate this column's values. Limited
    here to pass/fail (null while unanswered) — "partial" outcome is
    explicitly Phase 17 P17-D6 (undocumented threshold), not
    implemented.
    """

    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_session = models.ForeignKey(
        ReviewSession, on_delete=models.CASCADE, related_name="items"
    )
    concept = models.ForeignKey(
        "learning_content.Concept", on_delete=models.RESTRICT, related_name="review_items"
    )
    question_ref = models.ForeignKey(
        "learning_content.Exercise", on_delete=models.RESTRICT, related_name="review_items"
    )
    attempt = models.OneToOneField(
        "execution.ExerciseAttempt", on_delete=models.RESTRICT, null=True, blank=True,
        related_name="review_item",
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices, null=True, blank=True)

    class Meta:
        db_table = "review_items"
        indexes = [
            models.Index(fields=["review_session"], name="idx_ri_session"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(outcome__in=["pass", "fail"]) | models.Q(outcome__isnull=True),
                name="ck_review_items_outcome",
            ),
        ]

    def __str__(self):
        return f"ReviewItem({self.id}) session={self.review_session_id} concept={self.concept_id} outcome={self.outcome}"