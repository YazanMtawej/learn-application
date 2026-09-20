from unittest.mock import patch

from django.test import TestCase

from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import User
from apps.knowledge.models import ConceptFlawLog
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module
from apps.review.exceptions import ReviewContentUnavailableError
from apps.review.models import ReviewItem, ReviewSession
from apps.review.services import ReviewSessionService


def _module_with_weak_concept():
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published")
    concept = Concept.objects.create(name="Loops", base_difficulty=1)
    ExerciseConcept.objects.create(exercise=exercise, concept=concept)
    return module, concept


class SessionCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sessionuser@example.com", password="StrongPass123!")

    def test_module_completed_with_flagged_concept_creates_session_and_items(self):
        module, concept = _module_with_weak_concept()
        ConceptFlawLog.objects.create(
            user=self.user, concept=concept, error_type="conceptual", occurrence_count=5, flagged=True
        )
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=module.id
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.status, ReviewSession.Status.ACTIVE)
        self.assertEqual(session.items.count(), 1)

    def test_module_completed_with_no_weak_concepts_still_creates_confirmatory_session(self):
        module, concept = _module_with_weak_concept()
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=module.id
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.items.count(), 1)

    def test_adaptive_trigger_with_no_weak_concept_creates_no_session(self):
        _, concept = _module_with_weak_concept()
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "review_concept", target_concept_id=concept.id
        )
        self.assertIsNone(session)

    def test_module_completed_with_zero_published_content_raises_unavailable(self):
        module = Module.objects.create(title="Empty Module", order_index=2)
        with self.assertRaises(ReviewContentUnavailableError):
            ReviewSessionService.create_session_for_trigger(self.user, "module_completed", module_id=module.id)


class SessionSubmissionAndEvaluationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="submitreviewuser@example.com", password="StrongPass123!")
        self.module, self.concept = _module_with_weak_concept()

    def test_submitting_item_creates_linked_attempt(self):
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=self.module.id
        )
        item = session.items.first()
        with patch("apps.review.services.run_exercise_attempt.delay"):
            updated = ReviewSessionService.submit_item_answer(
                self.user, session.id, item.id, code="x=1", idempotency_key="rev-key-1"
            )
        self.assertIsNotNone(updated.attempt_id)

    def test_evaluation_result_updates_item_outcome_and_completes_session(self):
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=self.module.id
        )
        item = session.items.first()
        with patch("apps.review.services.run_exercise_attempt.delay"):
            ReviewSessionService.submit_item_answer(
                self.user, session.id, item.id, code="x=1", idempotency_key="rev-key-2"
            )

        attempt = ExerciseAttempt.objects.get(idempotency_key="rev-key-2")
        from django.utils import timezone

        Execution.objects.create(
            attempt=attempt, result_type="pass", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome="pass")

        item.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(item.outcome, "pass")
        self.assertEqual(session.status, ReviewSession.Status.COMPLETED)

    def test_failed_evaluation_moves_session_to_remediation(self):
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=self.module.id
        )
        item = session.items.first()
        with patch("apps.review.services.run_exercise_attempt.delay"):
            ReviewSessionService.submit_item_answer(
                self.user, session.id, item.id, code="x=1", idempotency_key="rev-key-3"
            )
        attempt = ExerciseAttempt.objects.get(idempotency_key="rev-key-3")
        from django.utils import timezone

        Execution.objects.create(
            attempt=attempt, result_type="fail", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome="fail")

        session.refresh_from_db()
        self.assertEqual(session.status, ReviewSession.Status.REMEDIATION)

    def test_resubmitting_answered_item_is_idempotent(self):
        session = ReviewSessionService.create_session_for_trigger(
            self.user, "module_completed", module_id=self.module.id
        )
        item = session.items.first()
        with patch("apps.review.services.run_exercise_attempt.delay"):
            ReviewSessionService.submit_item_answer(
                self.user, session.id, item.id, code="x=1", idempotency_key="rev-key-4"
            )
        first_attempt_id = ReviewItem.objects.get(id=item.id).attempt_id

        with patch("apps.review.services.run_exercise_attempt.delay") as mock_delay:
            ReviewSessionService.submit_item_answer(
                self.user, session.id, item.id, code="x=2", idempotency_key="rev-key-different"
            )
            mock_delay.assert_not_called()

        second_attempt_id = ReviewItem.objects.get(id=item.id).attempt_id
        self.assertEqual(first_attempt_id, second_attempt_id)


class EvidenceIntegrationTests(TestCase):
    def test_review_outcome_produces_evidence_via_reused_pipeline(self):
        from apps.knowledge.models import Evidence

        user = User.objects.create_user(email="evidencereviewuser@example.com", password="StrongPass123!")
        module, concept = _module_with_weak_concept()
        session = ReviewSessionService.create_session_for_trigger(user, "module_completed", module_id=module.id)
        item = session.items.first()

        with patch("apps.review.services.run_exercise_attempt.delay"):
            ReviewSessionService.submit_item_answer(user, session.id, item.id, code="x=1", idempotency_key="ev-key-1")

        attempt = ExerciseAttempt.objects.get(idempotency_key="ev-key-1")
        from django.utils import timezone

        Execution.objects.create(
            attempt=attempt, result_type="pass", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome="pass")

        self.assertTrue(Evidence.objects.filter(attempt=attempt, concept=concept, user=user).exists())

    def test_system_error_during_review_produces_no_evidence(self):
        from apps.knowledge.models import Evidence

        user = User.objects.create_user(email="reviewsyserr@example.com", password="StrongPass123!")
        module, concept = _module_with_weak_concept()
        session = ReviewSessionService.create_session_for_trigger(user, "module_completed", module_id=module.id)
        item = session.items.first()

        with patch("apps.review.services.run_exercise_attempt.delay"):
            ReviewSessionService.submit_item_answer(user, session.id, item.id, code="x=1", idempotency_key="ev-key-2")

        attempt = ExerciseAttempt.objects.get(idempotency_key="ev-key-2")
        from django.utils import timezone

        Execution.objects.create(
            attempt=attempt, result_type="system_error", started_at=timezone.now(), completed_at=timezone.now()
        )
        # No EvaluationResult created for system_error (Task 4 behavior).
        self.assertEqual(Evidence.objects.filter(attempt=attempt).count(), 0)


class AdaptiveTriggerIntegrationTests(TestCase):
    def test_adaptive_decision_review_concept_creates_session(self):
        user = User.objects.create_user(email="adaptivetriggeruser@example.com", password="StrongPass123!")
        _, concept = _module_with_weak_concept()
        ConceptFlawLog.objects.create(
            user=user, concept=concept, error_type="conceptual", occurrence_count=5, flagged=True
        )

        from apps.adaptive.models import AdaptiveDecision

        AdaptiveDecision.objects.create(
            user=user,
            trigger_event="submission_failed",
            signals_snapshot={},
            recommended_action={"type": "REVIEW_CONCEPT", "target_concept_id": str(concept.id), "target_module_id": None},
        )

        self.assertTrue(ReviewSession.objects.filter(user=user, trigger_context="review_concept").exists())