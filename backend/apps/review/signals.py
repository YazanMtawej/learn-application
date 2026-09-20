from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.adaptive.models import AdaptiveDecision
from apps.execution.models import EvaluationResult
from apps.review.candidates import ADAPTIVE_TRIGGERS
from apps.review.models import ReviewItem
from apps.review.services import ReviewSessionService


@receiver(post_save, sender=EvaluationResult)
def evaluation_result_updates_review_item(sender, instance, created, **kwargs):
    """
    Reads back the result of TASK 4's evaluation pipeline for the
    ExerciseAttempt this ReviewItem submitted (see
    ReviewSessionService.submit_item_answer). Zero modification to
    Task 4; zero duplicate grading logic (Phase 0 §9 Deterministic-
    First is honored by reuse, not re-implementation).
    """
    if not created:
        return

    review_item = getattr(instance.attempt, "review_item", None)
    if review_item is None:
        return  # not a review-originated attempt

    review_item.outcome = ReviewItem.Outcome.PASS if instance.outcome == "pass" else ReviewItem.Outcome.FAIL
    review_item.save(update_fields=["outcome"])

    ReviewSessionService.evaluate_session_completion(review_item.review_session)


@receiver(post_save, sender=AdaptiveDecision)
def adaptive_decision_triggers_review(sender, instance, created, **kwargs):
    """
    Phase 17 §6.A E4 Trigger: Adaptive Engine's REVIEW_CONCEPT /
    REVIEW_PREREQUISITE recommendation. F1 (active_flaw) is deliberately
    NOT wired as a trigger here — Phase 17 §6 confirms `review` must
    never launch a session from a Flaw signal alone. Zero modification
    to Task 6.
    """
    if not created:
        return

    action_type = instance.recommended_action.get("type")
    trigger_map = {"REVIEW_CONCEPT": "review_concept", "REVIEW_PREREQUISITE": "review_prerequisite"}
    trigger_context = trigger_map.get(action_type)
    if trigger_context is None:
        return

    target_concept_id = instance.recommended_action.get("target_concept_id")
    if target_concept_id is None:
        return

    ReviewSessionService.create_session_for_trigger(
        user=instance.user, trigger_context=trigger_context, target_concept_id=target_concept_id
    )