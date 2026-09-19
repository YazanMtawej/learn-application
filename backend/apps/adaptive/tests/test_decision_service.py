from django.test import TestCase, override_settings
from django.utils import timezone

from apps.adaptive import actions
from apps.adaptive.models import AdaptiveDecision
from apps.adaptive.services import AdaptiveDecisionService
from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import User
from apps.knowledge.models import Evidence
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module


def _make_exercise():
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(
        lesson=lesson, type="code_writing", difficulty=2,
        lifecycle_status=Exercise.LifecycleStatus.PUBLISHED,
    )
    concept = Concept.objects.create(name="Loops", base_difficulty=1)
    ExerciseConcept.objects.create(exercise=exercise, concept=concept)
    return exercise, concept


class AdaptiveDecisionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="adaptiveuser@example.com", password="StrongPass123!")
        self.exercise, self.concept = _make_exercise()

    def test_new_concept_without_evidence_yields_continue(self):
        decision = AdaptiveDecisionService.decide(
            self.user, trigger_event="submission_passed", concept_id=str(self.concept.id)
        )
        self.assertIn(decision.recommended_action["type"], {actions.CONTINUE, actions.PRACTICE_EASIER})

    def test_all_candidates_blocked_falls_back_to_stay(self):
        """Force unavailability by never publishing content tied to a fresh concept."""
        module = Module.objects.create(title="Blocked Module", order_index=99)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)  # draft, unpublished
        blocked_concept = Concept.objects.create(name="Blocked Concept", base_difficulty=1)
        ExerciseConcept.objects.create(exercise=exercise, concept=blocked_concept)

        decision = AdaptiveDecisionService.decide(
            self.user, trigger_event="submission_passed", concept_id=str(blocked_concept.id)
        )
        self.assertEqual(decision.recommended_action["type"], actions.STAY)
        self.assertIn("no eligible progression action", decision.signals_snapshot["reason"])

    def test_decision_is_append_only(self):
        AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        self.assertEqual(AdaptiveDecision.objects.filter(user=self.user).count(), 2)

    def test_decision_explainability_fields_present(self):
        decision = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        self.assertIn("reason", decision.signals_snapshot)
        self.assertIn("key_signals", decision.signals_snapshot)
        self.assertIn("ruleset_version", decision.signals_snapshot)

    def test_deterministic_repeated_identical_context_same_action(self):
        first = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        second = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        self.assertEqual(first.recommended_action["type"], second.recommended_action["type"])

    def test_ai_concept_signal_always_none_in_snapshot(self):
        decision = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        self.assertIsNone(decision.signals_snapshot["ai_concept_signal"])

    def test_cannot_update_existing_decision(self):
        from apps.adaptive.exceptions import AppendOnlyViolationError

        decision = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        decision.trigger_event = "tampered"
        with self.assertRaises(AppendOnlyViolationError):
            decision.save()

    def test_cannot_delete_existing_decision(self):
        from apps.adaptive.exceptions import AppendOnlyViolationError

        decision = AdaptiveDecisionService.decide(self.user, "submission_passed", str(self.concept.id))
        with self.assertRaises(AppendOnlyViolationError):
            decision.delete()


class EvaluationResultTriggersAdaptiveDecisionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="triggeruser@example.com", password="StrongPass123!")
        self.exercise, self.concept = _make_exercise()
        self.attempt = ExerciseAttempt.objects.create(
            user=self.user, exercise=self.exercise, code="x=1", attempt_number=1, idempotency_key="adapt-key"
        )

    def test_evaluation_result_creation_produces_adaptive_decision(self):
        Execution.objects.create(
            attempt=self.attempt, result_type="pass", started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=self.attempt, outcome="pass")
        self.assertTrue(AdaptiveDecision.objects.filter(user=self.user).exists())