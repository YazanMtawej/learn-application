import uuid

from django.conf import settings
from django.db import models

from apps.adaptive.exceptions import AppendOnlyViolationError


class AdaptiveDecision(models.Model):
    """
    CONFIRMED — Phase 8 §4.6 `adaptive_decisions` table, verbatim
    (id BIGSERIAL/Append-Only, user_id, trigger_event,
    signals_snapshot jsonb, recommended_action, created_at).

    Phase 16 §21 explicitly states that `reason`/`key_signals`/
    `ruleset_version` are "Conceptual Decision Metadata" with NO
    dedicated column in this schema, and must be embedded within
    `signals_snapshot`/`recommended_action` pending a future Schema
    Extension decision (Phase 21). This model follows that resolution
    literally — no new column is added here.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="adaptive_decisions"
    )
    trigger_event = models.CharField(max_length=50)
    signals_snapshot = models.JSONField()
    recommended_action = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adaptive_decisions"
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_ad_user_created"),
        ]

    def __str__(self):
        return f"AdaptiveDecision({self.id}) user={self.user_id} action={self.recommended_action.get('type')}"

    def save(self, *args, **kwargs):
        if self.pk is not None and AdaptiveDecision.objects.filter(pk=self.pk).exists():
            raise AppendOnlyViolationError("AdaptiveDecision records cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyViolationError("AdaptiveDecision records cannot be deleted.")