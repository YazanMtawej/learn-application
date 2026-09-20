import uuid

from django.conf import settings
from django.db import models


class Assessment(models.Model):
    """
    CONFIRMED — Phase 8 §4.8 `assessments` table, verbatim
    (id, module_id UNIQUE, max_attempts).

    No lifecycle/status field is documented for this table (unlike
    `exercises.lifecycle_status`) — this absence is treated as
    CONFIRMED, following the same pattern already established for
    `Module`/`Concept` in Task 3: an admin-managed entity with no
    draft/publish workflow.

    `max_attempts`: CONFIRMED as a real, required, Configurable column
    (Phase 8: "max_attempts (Configurable — OD-01, TBD رقميًا)") — the
    field exists, but no default numeric value is invented here
    (OD-01 explicitly leaves the number itself unresolved). It must be
    set explicitly per assessment.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.OneToOneField(
        "learning_content.Module", on_delete=models.RESTRICT, related_name="assessment"
    )
    max_attempts = models.PositiveIntegerField()

    class Meta:
        db_table = "assessments"

    def __str__(self):
        return f"Assessment({self.id}) module={self.module_id} max_attempts={self.max_attempts}"


class AssessmentItem(models.Model):
    """
    UNCONFIRMED BY DOCS — flagged Open Decision, same class as Task 8's
    `ReviewItem.question_ref`. Phase 7 §4.7 ASSESS-START response
    documents `questions[]` but no schema exists anywhere in Phase 8
    for an assessment question/item entity. Resolved identically to
    Task 8: reuse the existing `Exercise` entity (no bank/question
    entity is invented) with an explicit ordering field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(
        "learning_content.Exercise", on_delete=models.RESTRICT, related_name="assessment_items"
    )
    order_index = models.PositiveIntegerField()

    class Meta:
        db_table = "assessment_items"
        ordering = ["order_index"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "exercise"], name="uq_assessment_item_exercise"),
            models.UniqueConstraint(fields=["assessment", "order_index"], name="uq_assessment_item_order"),
        ]

    def __str__(self):
        return f"AssessmentItem({self.id}) assessment={self.assessment_id} exercise={self.exercise_id}"


class AssessmentAttempt(models.Model):
    """
    CONFIRMED — Phase 8 §4.8 `assessment_attempts` table, verbatim
    (id, assessment_id, user_id, attempt_number, result, created_at,
    UNIQUE(assessment_id, user_id, attempt_number)).

    Lifecycle matches Phase 2 SM-06 exactly:
    Not Started(no row) → In Progress → Passed
                                       → Failed → (retry, new row) In Progress
                                                → (exhausted) Remediation Required
                                                     → (after completion) In Progress
    """

    class Result(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.RESTRICT, related_name="attempts")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="assessment_attempts"
    )
    attempt_number = models.PositiveIntegerField()
    result = models.CharField(max_length=15, choices=Result.choices, default=Result.IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assessment_attempts"
        indexes = [
            models.Index(fields=["user"], name="idx_aa_user"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(result__in=["in_progress", "passed", "failed"]),
                name="ck_assessment_attempts_result",
            ),
            models.UniqueConstraint(
                fields=["assessment", "user", "attempt_number"], name="uq_aa_assessment_user_number"
            ),
        ]

    def __str__(self):
        return f"AssessmentAttempt({self.id}) user={self.user_id} #={self.attempt_number} result={self.result}"


class AssessmentResponse(models.Model):
    """
    UNCONFIRMED BY DOCS — ENGINEERING DECISION, not in Phase 8. Needed
    to link a submitted answer for one AssessmentItem, within one
    AssessmentAttempt, to the reused Task 4 execution pipeline
    (avoids duplicating deterministic evaluation logic — Phase 0 §9).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name="responses")
    item = models.ForeignKey(AssessmentItem, on_delete=models.RESTRICT, related_name="responses")
    exercise_attempt = models.OneToOneField(
        "execution.ExerciseAttempt", on_delete=models.RESTRICT, null=True, blank=True,
        related_name="assessment_response",
    )

    class Meta:
        db_table = "assessment_responses"
        constraints = [
            models.UniqueConstraint(fields=["attempt", "item"], name="uq_assessment_response_attempt_item"),
        ]

    def __str__(self):
        return f"AssessmentResponse({self.id}) attempt={self.attempt_id} item={self.item_id}"


class RemediationPath(models.Model):
    """
    CONFIRMED — Phase 8 §4.8 `remediation_paths` table, verbatim
    (id, assessment_attempt_id, status, created_at, completed_at).

    Only `required` and `completed` are actively transitioned to in
    this MVP implementation (`in_progress` remains a valid schema
    value per the documented CHECK constraint but has no distinct
    trigger defined anywhere in Phase 0-17 — honestly left unused
    rather than assigning it an invented meaning).
    """

    class Status(models.TextChoices):
        REQUIRED = "required", "Required"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_attempt = models.OneToOneField(
        AssessmentAttempt, on_delete=models.CASCADE, related_name="remediation_path"
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.REQUIRED)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "remediation_paths"
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=["required", "in_progress", "completed"]),
                name="ck_remediation_paths_status",
            ),
        ]

    def __str__(self):
        return f"RemediationPath({self.id}) attempt={self.assessment_attempt_id} status={self.status}"