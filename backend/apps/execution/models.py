import uuid

from django.conf import settings
from django.db import models

from apps.learning_content.models import Exercise


class ExerciseAttempt(models.Model):
    """CONFIRMED — Phase 8 §4.4 `exercise_attempts` table, verbatim."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exercise_attempts"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="attempts")
    code = models.TextField()
    attempt_number = models.PositiveIntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "exercise_attempts"
        indexes = [
            models.Index(fields=["user", "exercise"], name="idx_attempts_user_exercise"),
        ]

    def __str__(self):
        return f"ExerciseAttempt({self.id}) user={self.user_id} exercise={self.exercise_id}"


class Execution(models.Model):
    """
    CONFIRMED — Phase 8 §4.4 `executions` table, verbatim (attempt_id as
    1:1 PK/FK, result_type CHECK enum). ON DELETE RESTRICT (Phase 8)
    mapped to Django's PROTECT, consistent with the same mapping used
    for Plan FKs in Task 2.

    Absence of a row for a given attempt = still queued/running
    (Phase 9 §11 lifecycle: no Execution row exists until a terminal
    state — Completed/TimedOut/Failed/Cancelled — is reached).
    """

    class ResultType(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        TIMEOUT = "timeout", "Timeout"
        RUNTIME_ERROR = "runtime_error", "Runtime Error"
        SYSTEM_ERROR = "system_error", "System Error"
        CANCELLED = "cancelled", "Cancelled"

    attempt = models.OneToOneField(
        ExerciseAttempt, on_delete=models.PROTECT, primary_key=True, related_name="execution"
    )
    result_type = models.CharField(max_length=20, choices=ResultType.choices)
    raw_output_ref = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        db_table = "executions"
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    result_type__in=[
                        "pass", "fail", "timeout", "runtime_error", "system_error", "cancelled",
                    ]
                ),
                name="ck_executions_result_type",
            ),
        ]

    def __str__(self):
        return f"Execution(attempt={self.attempt_id}) result={self.result_type}"


class EvaluationResult(models.Model):
    """
    CONFIRMED — Phase 8 §4.4 `evaluation_results` table, verbatim.
    Created ONLY for result_type in {pass, fail, runtime_error} — never
    for timeout/system_error/cancelled (Phase 2 §4 / Phase 4 §7
    structural-failure rule, Phase 8 §8: "عند result_type IN
    ('timeout','system_error','cancelled') لا يُنشأ سجل evaluation_results
    أصلاً").
    """

    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"

    class ErrorType(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        CONCEPTUAL = "conceptual", "Conceptual"
        SYSTEM = "system", "System"

    attempt = models.OneToOneField(
        ExerciseAttempt, on_delete=models.PROTECT, primary_key=True, related_name="evaluation_result"
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    error_type = models.CharField(max_length=20, choices=ErrorType.choices, null=True, blank=True)
    details_ref = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "evaluation_results"
        indexes = [
            models.Index(fields=["outcome"], name="idx_eval_outcome"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(outcome__in=["pass", "fail"]), name="ck_evaluation_results_outcome"
            ),
            models.CheckConstraint(
                check=models.Q(error_type__in=["technical", "conceptual", "system"])
                | models.Q(error_type__isnull=True),
                name="ck_evaluation_results_error_type",
            ),
        ]

    def __str__(self):
        return f"EvaluationResult(attempt={self.attempt_id}) outcome={self.outcome}"