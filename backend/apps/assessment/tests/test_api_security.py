from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.assessment.models import Assessment, AssessmentItem
from apps.assessment.services import AssessmentAttemptService
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


def _build_assessment():
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published")
    assessment = Assessment.objects.create(module=module, max_attempts=2)
    AssessmentItem.objects.create(assessment=assessment, exercise=exercise, order_index=1)
    return module, assessment


class AssessmentAPISecurityTests(TestCase):
    def test_unauthenticated_start_rejected(self):
        module, _ = _build_assessment()
        anonymous_client = APIClient()
        response = anonymous_client.post(reverse("assessment:start", kwargs={"module_id": module.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_returns_attempt_with_questions(self):
        client, user = _active_client("assessapiuser@example.com")
        module, assessment = _build_assessment()
        response = client.post(reverse("assessment:start", kwargs={"module_id": module.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["data"]["questions"]), 1)

    def test_user_cannot_submit_to_another_users_attempt(self):
        owner_client, owner = _active_client("assessowner@example.com")
        module, assessment = _build_assessment()
        attempt = AssessmentAttemptService.start_attempt(owner, module.id)
        item = assessment.items.first()

        intruder_client, intruder = _active_client("assessintruder@example.com")
        url = reverse("assessment:submit", kwargs={"attempt_id": attempt.id})
        response = intruder_client.post(url, {"answers": [{"item_id": str(item.id), "code": "x=1"}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "ASSESSMENT_ATTEMPT_NOT_OWNED")

    def test_client_cannot_forge_result_via_request_body(self):
        client, user = _active_client("forgeresultuser@example.com")
        module, assessment = _build_assessment()
        attempt = AssessmentAttemptService.start_attempt(user, module.id)
        item = assessment.items.first()

        url = reverse("assessment:submit", kwargs={"attempt_id": attempt.id})
        with patch("apps.assessment.services.run_exercise_attempt.delay"):
            response = client.post(
                url,
                {
                    "answers": [{"item_id": str(item.id), "code": "x=1"}],
                    "result": "passed",
                    "remediation_required": False,
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        # Forged fields ignored entirely — result stays server-computed (still in_progress).
        self.assertEqual(response.data["data"]["result"], "in_progress")

    def test_cannot_access_another_users_attempt_status(self):
        owner_client, owner = _active_client("statusowner@example.com")
        module, assessment = _build_assessment()
        attempt = AssessmentAttemptService.start_attempt(owner, module.id)

        intruder_client, intruder = _active_client("statusintruder@example.com")
        url = reverse("assessment:attempt-status", kwargs={"attempt_id": attempt.id})
        response = intruder_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)