import uuid

from django.conf import settings
from django.db import models


class Hint(models.Model):
    """
    CONFIRMED — Phase 8 §4.7 `hints` table, verbatim
    (id, attempt_id, level 1-3, content, policy_check_result,
    delivered_at).

    Multiple rows per attempt are expected by design: rejected
    Post-Call Policy drafts (from the Regenerate loop, Phase 10 §11)
    are persisted as `policy_check_result='rejected'` rows (audit
    trail for Solution Leakage evaluation, Phase 3 RV-3), while the
    one row per level that is actually shown to the student is
    `policy_check_result='approved'` with `delivered_at` set.

    on_delete=RESTRICT on `attempt` per Phase 8 §12 ("ON DELETE
    RESTRICT كافتراضي لكل FK يشير لبيانات تعلم").
    """

    class PolicyResult(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        "execution.ExerciseAttempt", on_delete=models.RESTRICT, related_name="hints"
    )
    level = models.PositiveSmallIntegerField()
    content = models.TextField()
    policy_check_result = models.CharField(max_length=10, choices=PolicyResult.choices)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hints"
        indexes = [
            models.Index(fields=["attempt"], name="idx_hints_attempt"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(level__gte=1) & models.Q(level__lte=3), name="ck_hints_level"),
            models.CheckConstraint(
                check=models.Q(policy_check_result__in=["approved", "rejected"]),
                name="ck_hints_policy_check_result",
            ),
        ]

    def __str__(self):
        return f"Hint({self.id}) attempt={self.attempt_id} level={self.level} result={self.policy_check_result}"


class AIInteraction(models.Model):
    """
    CONFIRMED — Phase 8 §4.7 `ai_interactions` table, verbatim
    (id, user_id, use_case, model_version, cost, latency_ms,
    policy_result, created_at).

    `policy_result` choices extended beyond Hint's approved/rejected to
    include `unavailable`/`malformed` (ENGINEERING DECISION — Phase 8
    §4.7 does not enumerate this column's CHECK values explicitly in
    the abbreviated schema section; these additional values are needed
    to distinguish provider-availability failures from policy
    rejections for observability, per Phase 10 §18's own metric list
    which separately tracks `ai_unavailable` rate and Regenerate/
    rejection rate).

    One row is written per actual provider invocation (Phase 10 §16:
    Pre-Call-rejected requests never reach the provider and therefore
    never produce a row here).
    """

    class PolicyResult(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        UNAVAILABLE = "unavailable", "Unavailable"
        MALFORMED = "malformed", "Malformed"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="ai_interactions"
    )
    use_case = models.CharField(max_length=50)
    model_version = models.CharField(max_length=100)
    cost = models.FloatField(default=0.0)
    latency_ms = models.PositiveIntegerField(default=0)
    policy_result = models.CharField(max_length=15, choices=PolicyResult.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_interactions"
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_ai_user_created"),
        ]

    def __str__(self):
        return f"AIInteraction({self.id}) use_case={self.use_case} result={self.policy_result}"