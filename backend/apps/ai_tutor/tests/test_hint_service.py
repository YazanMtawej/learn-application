from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.ai_tutor.exceptions import (
    AttemptNotEvaluatedError,
    HintNotApplicableError,
    InvalidTransitionError,
)
from apps.ai_tutor.models import AIInteraction, Hint
from apps.ai_tutor.provider import AIResponse
from apps.ai_tutor.services import HintService
from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import User
from apps.learning_content.models import Exercise, Lesson, Module


def _make_attempt(outcome=None, key="hint-service-key"):
    user = User.objects.create_user(email=f"{key}@example.com", password="StrongPass123!")
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="code_writing", difficulty=1)
    attempt = ExerciseAttempt.objects.create(
        user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key=key
    )
    if outcome is not None:
        Execution.objects.create(
            attempt=attempt, result_type=outcome, started_at=timezone.now(), completed_at=timezone.now()
        )
        EvaluationResult.objects.create(attempt=attempt, outcome=outcome)
    return user, attempt


class HintServiceEligibilityTests(TestCase):
    def test_unevaluated_attempt_raises(self):
        user, attempt = _make_attempt(outcome=None, key="unevaluated")
        with self.assertRaises(AttemptNotEvaluatedError):
            HintService.request_hint(user, attempt.id)

    def test_passed_attempt_raises_not_applicable(self):
        user, attempt = _make_attempt(outcome="pass", key="passed-attempt")
        with self.assertRaises(HintNotApplicableError):
            HintService.request_hint(user, attempt.id)


class HintServiceProviderUnavailableTests(TestCase):
    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_unavailable_provider_returns_fallback_without_creating_hint(self, mock_build):
        user, attempt = _make_attempt(outcome="fail", key="unavailable-provider")
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(available=False)

        result = HintService.request_hint(user, attempt.id)
        self.assertFalse(result.delivered)
        self.assertEqual(result.status, "ai_unavailable")
        self.assertEqual(Hint.objects.filter(attempt=attempt).count(), 0)
        self.assertTrue(AIInteraction.objects.filter(user=user, policy_result="unavailable").exists())


class HintServiceHappyPathTests(TestCase):
    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_approved_response_creates_delivered_hint(self, mock_build):
        user, attempt = _make_attempt(outcome="fail", key="happy-path")
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(
            available=True, content="Consider what your loop condition evaluates to.", model_version="test-model"
        )

        result = HintService.request_hint(user, attempt.id)
        self.assertTrue(result.delivered)
        self.assertEqual(result.hint_level, 1)

        hint = Hint.objects.get(attempt=attempt)
        self.assertEqual(hint.policy_check_result, "approved")
        self.assertIsNotNone(hint.delivered_at)

    @override_settings(AI_HINT_CODE_LINE_THRESHOLD=3, AI_REGENERATE_MAX_ATTEMPTS=1)
    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_leaky_response_is_regenerated_then_falls_back(self, mock_build):
        user, attempt = _make_attempt(outcome="fail", key="leaky-response")
        leaky_content = "```python\n" + "\n".join([f"line{i}=1" for i in range(10)]) + "\n```"
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(available=True, content=leaky_content)

        result = HintService.request_hint(user, attempt.id)
        self.assertFalse(result.delivered)
        self.assertEqual(result.status, "ai_unavailable")
        # Two rejected drafts logged (initial + one regenerate), no approved Hint.
        self.assertEqual(Hint.objects.filter(attempt=attempt, policy_check_result="rejected").count(), 2)
        self.assertEqual(Hint.objects.filter(attempt=attempt, policy_check_result="approved").count(), 0)

    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_third_level_request_after_exhaustion_raises_invalid_transition(self, mock_build):
        user, attempt = _make_attempt(outcome="fail", key="exhaustion-key")
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(available=True, content="General guidance text here.")

        HintService.request_hint(user, attempt.id)
        HintService.request_hint(user, attempt.id)
        HintService.request_hint(user, attempt.id)

        with self.assertRaises(InvalidTransitionError):
            HintService.request_hint(user, attempt.id)