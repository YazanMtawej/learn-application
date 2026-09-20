from django.db import IntegrityError
from django.test import TestCase

from apps.ai_tutor.models import AIInteraction, Hint
from apps.execution.models import ExerciseAttempt
from apps.identity.models import User
from apps.learning_content.models import Exercise, Lesson, Module


class HintModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="hintmodeluser@example.com", password="StrongPass123!")
        module = Module.objects.create(title="Fundamentals", order_index=1)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)
        self.attempt = ExerciseAttempt.objects.create(
            user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key="hint-model-key"
        )

    def test_invalid_level_rejected_by_constraint(self):
        hint = Hint.objects.create(attempt=self.attempt, level=1, content="x", policy_check_result="approved")
        hint.level = 5
        with self.assertRaises(IntegrityError):
            hint.save()

    def test_invalid_policy_result_rejected_by_constraint(self):
        hint = Hint.objects.create(attempt=self.attempt, level=1, content="x", policy_check_result="approved")
        hint.policy_check_result = "not_a_real_value"
        with self.assertRaises(IntegrityError):
            hint.save()

    def test_multiple_hints_per_attempt_allowed(self):
        Hint.objects.create(attempt=self.attempt, level=1, content="a", policy_check_result="rejected")
        Hint.objects.create(attempt=self.attempt, level=1, content="b", policy_check_result="approved")
        self.assertEqual(Hint.objects.filter(attempt=self.attempt).count(), 2)


class AIInteractionModelTests(TestCase):
    def test_interaction_created_with_defaults(self):
        user = User.objects.create_user(email="aiinteractionuser@example.com", password="StrongPass123!")
        interaction = AIInteraction.objects.create(
            user=user, use_case="hint_generation", model_version="none", policy_result="unavailable"
        )
        self.assertEqual(interaction.cost, 0.0)
        self.assertEqual(interaction.latency_ms, 0)