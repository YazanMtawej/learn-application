from unittest.mock import patch

from django.test import TestCase

from apps.assessment.exceptions import (
    AssessmentAlreadyPassedError,
    AttemptInProgressError,
    RemediationRequiredError,
)
from apps.assessment.models import Assessment, AssessmentAttempt, AssessmentItem
from apps.assessment.services import AssessmentAttemptService, AssessmentEligibilityService
from apps.execution.models import EvaluationResult, Execution
from apps.identity.models import User
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module
from apps.review.models import ReviewSession


def _build(max_attempts=2):
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published")
    concept = Concept.objects.create(name="Loops", base_difficulty=1)
    ExerciseConcept.objects.create(exercise=exercise, concept=concept)
    assessment = Assessment.objects.create(module=module, max_attempts=max_attempts)
    AssessmentItem.objects.create(assessment=assessment, exercise=exercise, order_index=1)
    return module, assessment, exercise


class EligibilityTests(TestCase):
    def test_first_attempt_allowed_at_number_one(self):
        _, assessment, _ = _build()
        user = User.objects.create_user(email="elig1@example.com", password="StrongPass123!")
        self.assertEqual(AssessmentEligibilityService.resolve_next_attempt_number(assessment, user), 1)

    def test_in_progress_attempt_blocks_new_attempt(self):
        _, assessment, _ = _build()
        user = User.objects.create_user(email="elig2@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1)
        with self.assertRaises(AttemptInProgressError):
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)

    def test_passed_attempt_blocks_retake(self):
        _, assessment, _ = _build()
        user = User.objects.create_user(email="elig3@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1, result="passed")
        with self.assertRaises(AssessmentAlreadyPassedError):
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)

    def test_failed_attempt_with_remaining_attempts_allows_retry(self):
        _, assessment, _ = _build(max_attempts=2)
        user = User.objects.create_user(email="elig4@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1, result="failed")
        self.assertEqual(AssessmentEligibilityService.resolve_next_attempt_number(assessment, user), 2)

    def test_attempts_exhausted_without_remediation_blocks_with_remediation_required(self):
        module, assessment, exercise = _build(max_attempts=1)
        user = User.objects.create_user(email="elig5@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1, result="failed")
        with self.assertRaises(RemediationRequiredError):
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)

    def test_remediation_path_created_on_first_exhaustion_check(self):
        from apps.assessment.models import RemediationPath

        module, assessment, exercise = _build(max_attempts=1)
        user = User.objects.create_user(email="elig6@example.com", password="StrongPass123!")
        attempt = AssessmentAttempt.objects.create(
            assessment=assessment, user=user, attempt_number=1, result="failed"
        )
        with self.assertRaises(RemediationRequiredError):
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)
        self.assertTrue(RemediationPath.objects.filter(assessment_attempt=attempt).exists())

    def test_completed_remediation_grants_exactly_one_additional_attempt(self):
        module, assessment, exercise = _build(max_attempts=1)
        user = User.objects.create_user(email="elig7@example.com", password="StrongPass123!")
        attempt = AssessmentAttempt.objects.create(
            assessment=assessment, user=user, attempt_number=1, result="failed"
        )
        with self.assertRaises(RemediationRequiredError):
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)

        from apps.assessment.models import RemediationPath

        remediation = RemediationPath.objects.get(assessment_attempt=attempt)
        ReviewSession.objects.create(
            user=user, trigger_context="assessment_remediation", status=ReviewSession.Status.COMPLETED
        )

        next_number = AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)
        self.assertEqual(next_number, 2)

    def test_no_permanent_block_dead_end(self):
        """Phase 2 §26 Invariant: never a permanent block."""
        module, assessment, exercise = _build(max_attempts=1)
        user = User.objects.create_user(email="elig8@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1, result="failed")
        try:
            AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)
        except RemediationRequiredError:
            pass  # Expected — but a path forward (remediation) exists, not a dead end.
        ReviewSession.objects.create(
            user=user, trigger_context="assessment_remediation", status=ReviewSession.Status.COMPLETED
        )
        # Path forward now succeeds:
        self.assertEqual(AssessmentEligibilityService.resolve_next_attempt_number(assessment, user), 2)


class SubmissionAndFinalizationTests(TestCase):
    def test_submit_creates_linked_exercise_attempts(self):
        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit1@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        item = assessment.items.first()

        with patch("apps.assessment.services.run_exercise_attempt.delay"):
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=1"}], "idem-1"
            )

        response = attempt.responses.get(item=item)
        self.assertIsNotNone(response.exercise_attempt_id)

    def test_all_items_pass_finalizes_attempt_as_passed(self):
        from django.utils import timezone

        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit2@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        item = assessment.items.first()

        with patch("apps.assessment.services.run_exercise_attempt.delay"):
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=1"}], "idem-2"
            )

        response = attempt.responses.get(item=item)
        Execution.objects.create(
            attempt=response.exercise_attempt, result_type="pass",
            started_at=timezone.now(), completed_at=timezone.now(),
        )
        EvaluationResult.objects.create(attempt=response.exercise_attempt, outcome="pass")

        attempt.refresh_from_db()
        self.assertEqual(attempt.result, "passed")

    def test_any_item_fails_finalizes_attempt_as_failed(self):
        from django.utils import timezone

        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit3@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        item = assessment.items.first()

        with patch("apps.assessment.services.run_exercise_attempt.delay"):
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=1"}], "idem-3"
            )

        response = attempt.responses.get(item=item)
        Execution.objects.create(
            attempt=response.exercise_attempt, result_type="fail",
            started_at=timezone.now(), completed_at=timezone.now(),
        )
        EvaluationResult.objects.create(attempt=response.exercise_attempt, outcome="fail")

        attempt.refresh_from_db()
        self.assertEqual(attempt.result, "failed")

    def test_resubmitting_answered_item_is_idempotent(self):
        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit4@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        item = assessment.items.first()

        with patch("apps.assessment.services.run_exercise_attempt.delay"):
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=1"}], "idem-4"
            )
        first_id = attempt.responses.get(item=item).exercise_attempt_id

        with patch("apps.assessment.services.run_exercise_attempt.delay") as mock_delay:
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=999"}], "idem-4-different"
            )
            mock_delay.assert_not_called()

        second_id = attempt.responses.get(item=item).exercise_attempt_id
        self.assertEqual(first_id, second_id)

    def test_invalid_item_id_rejected(self):
        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit5@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        from apps.assessment.exceptions import InvalidItemError

        with self.assertRaises(InvalidItemError):
            AssessmentAttemptService.submit_answers(
                user, attempt.id,
                [{"item_id": "00000000-0000-0000-0000-000000000000", "code": "x=1"}],
                "idem-5",
            )

    def test_submitting_to_finalized_attempt_rejected(self):
        module, assessment, exercise = _build()
        user = User.objects.create_user(email="submit6@example.com", password="StrongPass123!")
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        attempt.result = "passed"
        attempt.save(update_fields=["result"])

        item = assessment.items.first()
        from apps.assessment.exceptions import AttemptNotActiveError

        with self.assertRaises(AttemptNotActiveError):
            AssessmentAttemptService.submit_answers(
                user, attempt.id, [{"item_id": item.id, "code": "x=1"}], "idem-6"
            )