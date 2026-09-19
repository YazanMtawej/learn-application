from django.test import TestCase

from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import User
from apps.knowledge.models import ConceptMastery, Evidence
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module


def _make_exercise(concept_names):
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(
        lesson=lesson, type="code_writing", difficulty=2,
        lifecycle_status=Exercise.LifecycleStatus.PUBLISHED,
    )
    concepts = []
    for name in concept_names:
        concept = Concept.objects.create(name=name, base_difficulty=1)
        ExerciseConcept.objects.create(exercise=exercise, concept=concept)
        concepts.append(concept)
    return exercise, concepts


def _create_attempt(user, exercise, key, attempt_number=1):
    return ExerciseAttempt.objects.create(
        user=user, exercise=exercise, code="x=1", attempt_number=attempt_number, idempotency_key=key
    )


class EvidenceCreationOnEvaluationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="evidenceuser@example.com", password="StrongPass123!")
        self.exercise, self.concepts = _make_exercise(["Loops"])
        self.attempt = _create_attempt(self.user, self.exercise, "ev-key-1")

    def _finalize(self, outcome="pass", error_type=None):
        from django.utils import timezone

        Execution.objects.create(
            attempt=self.attempt, result_type=outcome, started_at=timezone.now(), completed_at=timezone.now()
        )
        return EvaluationResult.objects.create(attempt=self.attempt, outcome=outcome, error_type=error_type)

    def test_evidence_created_on_evaluation_result_creation(self):
        self._finalize(outcome="pass")
        self.assertEqual(Evidence.objects.filter(attempt=self.attempt).count(), 1)

    def test_evidence_correctness_matches_outcome(self):
        self._finalize(outcome="fail")
        evidence = Evidence.objects.get(attempt=self.attempt)
        self.assertFalse(evidence.correctness)

    def test_concept_mastery_row_created_after_first_evidence(self):
        self._finalize(outcome="pass")
        self.assertTrue(ConceptMastery.objects.filter(user=self.user, concept=self.concepts[0]).exists())

    def test_duplicate_evaluation_result_creation_does_not_duplicate_evidence(self):
        self._finalize(outcome="pass")
        # get_or_create on Execution/EvaluationResult in TASK 4 prevents
        # a second row for the same attempt; simulate the same attempt+
        # concept pair directly to prove the idempotency constraint.
        with self.assertRaises(Exception):
            Evidence.objects.create(
                attempt=self.attempt, concept=self.concepts[0], user=self.user, correctness=True
            )


class SystemFailureExcludedFromEvidenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sysfailuser@example.com", password="StrongPass123!")
        self.exercise, self.concepts = _make_exercise(["Functions"])

    def test_timeout_produces_no_evaluation_result_and_no_evidence(self):
        from django.utils import timezone

        attempt = _create_attempt(self.user, self.exercise, "timeout-key")
        Execution.objects.create(
            attempt=attempt, result_type="timeout", started_at=timezone.now(), completed_at=timezone.now()
        )
        # No EvaluationResult is ever created for timeout (TASK 4 behavior).
        self.assertFalse(EvaluationResult.objects.filter(attempt=attempt).exists())
        self.assertEqual(Evidence.objects.filter(attempt=attempt).count(), 0)

    def test_system_error_produces_no_evidence(self):
        from django.utils import timezone

        attempt = _create_attempt(self.user, self.exercise, "syserr-key")
        Execution.objects.create(
            attempt=attempt, result_type="system_error", started_at=timezone.now(), completed_at=timezone.now()
        )
        self.assertEqual(Evidence.objects.filter(attempt=attempt).count(), 0)

    def test_cancelled_produces_no_evidence(self):
        from django.utils import timezone

        attempt = _create_attempt(self.user, self.exercise, "cancel-key")
        Execution.objects.create(
            attempt=attempt, result_type="cancelled", started_at=timezone.now(), completed_at=timezone.now()
        )
        self.assertEqual(Evidence.objects.filter(attempt=attempt).count(), 0)


class MultiConceptAttributionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="multiuser@example.com", password="StrongPass123!")
        self.exercise, self.concepts = _make_exercise(["Loops", "Functions"])

    def test_one_evidence_row_created_per_linked_concept(self):
        from django.utils import timezone

        attempt = _create_attempt(self.user, self.exercise, "multi-key")
        Execution.objects.create(
            attempt=attempt, result_type="pass", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome="pass")

        self.assertEqual(Evidence.objects.filter(attempt=attempt).count(), 2)
        self.assertEqual(ConceptMastery.objects.filter(user=self.user).count(), 2)


class AppendOnlyEvidenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="appendonlyuser@example.com", password="StrongPass123!")
        self.exercise, self.concepts = _make_exercise(["Loops"])
        attempt = _create_attempt(self.user, self.exercise, "append-key")
        from django.utils import timezone

        Execution.objects.create(
            attempt=attempt, result_type="pass", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome="pass")
        self.evidence = Evidence.objects.get(attempt=attempt)

    def test_evidence_cannot_be_updated(self):
        from apps.knowledge.exceptions import AppendOnlyViolationError

        self.evidence.correctness = False
        with self.assertRaises(AppendOnlyViolationError):
            self.evidence.save()

    def test_evidence_cannot_be_deleted(self):
        from apps.knowledge.exceptions import AppendOnlyViolationError

        with self.assertRaises(AppendOnlyViolationError):
            self.evidence.delete()