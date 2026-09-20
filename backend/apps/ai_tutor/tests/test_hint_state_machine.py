from django.test import TestCase

from apps.ai_tutor.exceptions import InvalidTransitionError
from apps.ai_tutor.hint_state import HintStateMachine
from apps.ai_tutor.models import Hint
from apps.execution.models import ExerciseAttempt
from apps.identity.models import User
from apps.learning_content.models import Exercise, Lesson, Module


class HintStateMachineTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="statemachineuser@example.com", password="StrongPass123!")
        module = Module.objects.create(title="Fundamentals", order_index=1)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)
        self.attempt = ExerciseAttempt.objects.create(
            user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key="sm-key"
        )

    def test_no_hints_yet_current_level_is_zero(self):
        self.assertEqual(HintStateMachine.get_current_level(self.attempt), 0)

    def test_first_request_targets_level_one(self):
        next_level = HintStateMachine.validate_and_get_next_level(self.attempt)
        self.assertEqual(next_level, 1)

    def test_rejected_hints_do_not_advance_current_level(self):
        Hint.objects.create(attempt=self.attempt, level=1, content="x", policy_check_result="rejected")
        self.assertEqual(HintStateMachine.get_current_level(self.attempt), 0)

    def test_approved_hint_advances_current_level(self):
        Hint.objects.create(attempt=self.attempt, level=1, content="x", policy_check_result="approved")
        self.assertEqual(HintStateMachine.get_current_level(self.attempt), 1)
        self.assertEqual(HintStateMachine.validate_and_get_next_level(self.attempt), 2)

    def test_cannot_skip_levels(self):
        # No level-2/3 request field exists on the API — the state
        # machine itself always returns exactly current+1, so skipping
        # is structurally impossible via this service.
        Hint.objects.create(attempt=self.attempt, level=1, content="x", policy_check_result="approved")
        next_level = HintStateMachine.validate_and_get_next_level(self.attempt)
        self.assertEqual(next_level, 2)

    def test_exhausted_levels_raise_invalid_transition(self):
        for level in (1, 2, 3):
            Hint.objects.create(attempt=self.attempt, level=level, content="x", policy_check_result="approved")
        with self.assertRaises(InvalidTransitionError):
            HintStateMachine.validate_and_get_next_level(self.attempt)