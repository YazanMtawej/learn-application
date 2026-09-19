import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.execution.models import ExerciseAttempt
from apps.knowledge.exceptions import AppendOnlyViolationError
from apps.learning_content.models import Concept


class Evidence(models.Model):
    """
    CONFIRMED — Phase 8 §4.5 `evidence` table, verbatim
    (id BIGSERIAL/Append-Only, user_id, concept_id, attempt_id nullable,
    correctness, hint_usage, error_type, created_at).

    Phase 15 §6.3 lists additional conceptual fields (source_type,
    source_id, attempt_number, exercise_difficulty, exercise_type) but
    explicitly states these are "مفاهيمي... بلا Schema جديد" — they are
    exposed below as derived Python properties computed via the
    `attempt` relation, never as stored columns, to avoid adding
    undocumented schema.

    `hint_usage` is currently always 0: no Hint/AI Tutor system exists
    yet (out of TASK 5 scope) to populate it. This is a documented
    limitation, not fabricated data.

    on_delete=RESTRICT on user/concept/attempt per Phase 8 §12:
    "ON DELETE RESTRICT كافتراضي لكل FK يشير لبيانات تعلم (exercise_attempts,
    evidence, إلخ) — لا Cascade Delete".
    """

    class ErrorType(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        CONCEPTUAL = "conceptual", "Conceptual"
        SYSTEM = "system", "System"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="evidence_records"
    )
    concept = models.ForeignKey(Concept, on_delete=models.RESTRICT, related_name="evidence_records")
    attempt = models.ForeignKey(
        ExerciseAttempt, on_delete=models.RESTRICT, null=True, blank=True, related_name="evidence_records"
    )
    correctness = models.BooleanField()
    hint_usage = models.PositiveSmallIntegerField(default=0)
    error_type = models.CharField(max_length=20, choices=ErrorType.choices, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evidence"
        indexes = [
            models.Index(fields=["user", "concept"], name="idx_evidence_user_concept"),
            models.Index(fields=["created_at"], name="idx_evidence_created_at"),
        ]
        constraints = [
            # ENGINEERING DECISION — Phase 15 §17: "كل سجل Evidence
            # مرتبط بمعرّف حدث مصدر فريد... يمنع ازدواج الاحتساب لنفس
            # الحدث". Phase 8 does not name this constraint explicitly;
            # this implements the mandated behavior. Scoped to
            # (attempt, concept) rather than attempt alone, because
            # Equal Attribution (Phase 15 §5/P15-D1) produces one
            # Evidence row per linked concept for a multi-concept
            # exercise attempt.
            models.UniqueConstraint(
                fields=["attempt", "concept"],
                condition=models.Q(attempt__isnull=False),
                name="uq_evidence_attempt_concept",
            ),
        ]

    def __str__(self):
        return f"Evidence({self.id}) user={self.user_id} concept={self.concept_id}"

    @property
    def source_type(self):
        """DERIVED, not stored — Phase 15 §6.3."""
        return "exercise_attempt" if self.attempt_id else None

    @property
    def source_id(self):
        """DERIVED, not stored — Phase 15 §6.3."""
        return self.attempt_id

    @property
    def attempt_number(self):
        return self.attempt.attempt_number if self.attempt_id else None

    @property
    def exercise_difficulty(self):
        return self.attempt.exercise.difficulty if self.attempt_id else None

    @property
    def exercise_type(self):
        return self.attempt.exercise.type if self.attempt_id else None

    def save(self, *args, **kwargs):
        if self.pk is not None and Evidence.objects.filter(pk=self.pk).exists():
            raise AppendOnlyViolationError("Evidence records cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyViolationError("Evidence records cannot be deleted.")


class ConceptMastery(models.Model):
    """
    CONFIRMED fields — Phase 8 §4.5 `concept_mastery` table
    ((user_id, concept_id) composite PK, mastery_value jsonb,
    updated_at).

    Composite PK not supported in this Django version — same surrogate
    UUID PK + UniqueConstraint(user, concept) pattern already used for
    ExerciseConcept in TASK 3 (documented there as an ENGINEERING
    DECISION for the same structural reason).

    `mastery_value` stores the full Phase 15 §19 conceptual output
    (state, score, evidence_summary, reason, review_recommended,
    algorithm_version) as jsonb — matching Phase 8's own description
    ("jsonb متعدد الأبعاد يسمح بإضافة أبعاد لاحقًا دون Migration جذرية").
    `active_flaw` is intentionally NOT duplicated here — it is always
    read live from ConceptFlawLog (Phase 4 §14: ConceptFlawLog owns
    that state, not Knowledge & Mastery's cache of it).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="concept_masteries"
    )
    concept = models.ForeignKey(Concept, on_delete=models.RESTRICT, related_name="masteries")
    mastery_value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "concept_mastery"
        indexes = [
            models.Index(fields=["user"], name="idx_cm_user"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "concept"], name="uq_concept_mastery_user_concept"),
        ]

    def __str__(self):
        return f"ConceptMastery(user={self.user_id}, concept={self.concept_id})"


class ConceptFlawLog(models.Model):
    """CONFIRMED — Phase 8 §4.5 `concept_flaw_log` table, verbatim."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="concept_flaws"
    )
    concept = models.ForeignKey(Concept, on_delete=models.RESTRICT, related_name="flaw_logs")
    error_type = models.CharField(max_length=20, choices=Evidence.ErrorType.choices)
    occurrence_count = models.PositiveIntegerField(default=0)
    flagged = models.BooleanField(default=False)
    first_detected_at = models.DateTimeField(auto_now_add=True)
    last_detected_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "concept_flaw_log"
        indexes = [
            models.Index(fields=["flagged"], name="idx_flaw_flagged"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "concept", "error_type"], name="uq_flaw_user_concept_errortype"
            ),
        ]

    def __str__(self):
        return f"ConceptFlawLog(user={self.user_id}, concept={self.concept_id}, flagged={self.flagged})"

    def register_occurrence(self, threshold: int):
        self.occurrence_count += 1
        self.last_detected_at = timezone.now()
        if self.occurrence_count >= threshold:
            self.flagged = True
        self.save(update_fields=["occurrence_count", "last_detected_at", "flagged"])