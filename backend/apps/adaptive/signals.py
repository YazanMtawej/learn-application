from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.adaptive.services import AdaptiveDecisionService
from apps.execution.models import EvaluationResult


@receiver(post_save, sender=EvaluationResult)
def evaluation_result_triggers_adaptive_decision(sender, instance, created, **kwargs):
    """
    Server-side trigger only (Phase 16 §28: no client-facing endpoint
    can invoke a decision). Runs after TASK 5's own EvaluationResult
    signal handler in the same Django signal dispatch (both are
    `post_save` receivers on the same sender; Django calls receivers
    in registration order within the same transaction TASK 4 opened —
    no new transaction boundary introduced).

    ExerciseEvaluated (Phase 4 §13) is consumed by both Knowledge &
    Mastery (TASK 5) and Adaptive Learning (this task) — matching
    Phase 4 §13's own event table exactly.
    """
    if not created:
        return

    attempt = instance.attempt
    exercise = attempt.exercise
    trigger_event = "submission_passed" if instance.outcome == "pass" else "submission_failed"

    concept_ids = list(exercise.concepts.values_list("id", flat=True))
    for concept_id in concept_ids:
        AdaptiveDecisionService.decide(
            user=attempt.user, trigger_event=trigger_event, concept_id=str(concept_id)
        )