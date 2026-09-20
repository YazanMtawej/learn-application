from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.assessment.services import AssessmentAttemptService
from apps.execution.models import EvaluationResult


@receiver(post_save, sender=EvaluationResult)
def evaluation_result_finalizes_assessment_attempt(sender, instance, created, **kwargs):
    """
    Reads back Task 4's evaluation pipeline result for the
    ExerciseAttempt this AssessmentResponse submitted. Zero
    modification to Task 4; zero duplicated grading logic.
    """
    if not created:
        return

    assessment_response = getattr(instance.attempt, "assessment_response", None)
    if assessment_response is None:
        return  # not an assessment-originated attempt

    AssessmentAttemptService.finalize_if_ready(assessment_response.attempt)