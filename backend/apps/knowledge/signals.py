from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.execution.models import EvaluationResult
from apps.knowledge.services import EvidenceIngestionService


@receiver(post_save, sender=EvaluationResult)
def evaluation_result_created(sender, instance, created, **kwargs):
    """
    CONFIRMED — Phase 4 §13 `ExerciseEvaluated` event, consumed by
    Knowledge & Mastery. TASK 4's `EvaluationResult` is only ever
    created for {pass, fail, runtime_error} outcomes (never for
    timeout/system_error/cancelled, which never produce an
    EvaluationResult row at all) — this structurally satisfies Phase 9
    C10 / Phase 15 §6.3's invariant that system/infra failures never
    produce Evidence, with no extra guard needed here.
    """
    if not created:
        return
    EvidenceIngestionService.ingest_from_evaluation(instance)