from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.ai_tutor.provider import AIResponse
from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.learning_content.models import Exercise, Lesson, Module


def _active_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


def _failed_attempt(user):
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="code_writing", difficulty=1)
    attempt = ExerciseAttempt.objects.create(
        user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key=f"api-{user.id}"
    )
    Execution.objects.create(
        attempt=attempt, result_type="fail", started_at=timezone.now(), completed_at=timezone.now()
    )
    EvaluationResult.objects.create(attempt=attempt, outcome="fail")
    return attempt


class HintAPISecurityTests(TestCase):
    def test_unauthenticated_hint_request_rejected(self):
        client, user = _active_client("apiowner@example.com")
        attempt = _failed_attempt(user)
        anonymous_client = APIClient()
        url = reverse("ai_tutor:hint-request", kwargs={"attempt_id": attempt.id})
        response = anonymous_client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_request_hint_for_another_users_attempt(self):
        owner_client, owner = _active_client("hintowner@example.com")
        attempt = _failed_attempt(owner)

        other_client, other = _active_client("hintintruder@example.com")
        url = reverse("ai_tutor:hint-request", kwargs={"attempt_id": attempt.id})
        response = other_client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "ATTEMPT_NOT_OWNED")

    def test_user_cannot_read_hint_state_for_another_users_attempt(self):
        owner_client, owner = _active_client("stateowner@example.com")
        attempt = _failed_attempt(owner)

        other_client, other = _active_client("stateintruder@example.com")
        url = reverse("ai_tutor:hint-state", kwargs={"attempt_id": attempt.id})
        response = other_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_client_cannot_control_hint_level_via_request_body(self, mock_build):
        """
        The API accepts no level parameter at all — attempting to inject
        one has no effect; the server always computes the next level
        itself (Phase 16 §28 Security).
        """
        client, user = _active_client("levelinjector@example.com")
        attempt = _failed_attempt(user)
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(available=True, content="General nudge text.")

        url = reverse("ai_tutor:hint-request", kwargs={"attempt_id": attempt.id})
        response = client.post(url, {"level": 3, "hint_level": 3}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["hint_level"], 1)

    @patch("apps.ai_tutor.services.build_ai_provider")
    def test_hint_response_never_exposes_system_prompt_layers(self, mock_build):
        client, user = _active_client("promptleakuser@example.com")
        attempt = _failed_attempt(user)
        fake_provider = mock_build.return_value
        fake_provider.generate_hint.return_value = AIResponse(available=True, content="A safe general hint.")

        url = reverse("ai_tutor:hint-request", kwargs={"attempt_id": attempt.id})
        response = client.post(url, {}, format="json")
        self.assertNotIn("SYSTEM_POLICY_LAYER", str(response.data))
        self.assertNotIn("EDUCATIONAL_POLICY_LAYER", str(response.data))