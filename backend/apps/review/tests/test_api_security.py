from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.knowledge.models import ConceptFlawLog
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module
from apps.review.services import ReviewSessionService


def _active_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


def _module_with_weak_concept(user):
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published")
    concept = Concept.objects.create(name="Loops", base_difficulty=1)
    ExerciseConcept.objects.create(exercise=exercise, concept=concept)
    ConceptFlawLog.objects.create(
        user=user, concept=concept, error_type="conceptual", occurrence_count=5, flagged=True
    )
    return module


class ReviewAPISecurityTests(TestCase):
    def test_unauthenticated_start_rejected(self):
        module = Module.objects.create(title="M", order_index=1)
        anonymous_client = APIClient()
        response = anonymous_client.post(reverse("review:start"), {"module_id": str(module.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_returns_session_with_items(self):
        client, user = _active_client("reviewapiuser@example.com")
        module = _module_with_weak_concept(user)
        response = client.post(reverse("review:start"), {"module_id": str(module.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_user_cannot_submit_to_another_users_session(self):
        owner_client, owner = _active_client("reviewowner@example.com")
        module = _module_with_weak_concept(owner)
        session = ReviewSessionService.create_session_for_trigger(owner, "module_completed", module_id=module.id)
        item = session.items.first()

        intruder_client, intruder = _active_client("reviewintruder@example.com")
        url = reverse("review:submit-item", kwargs={"session_id": session.id, "item_id": item.id})
        response = intruder_client.post(url, {"answer": "x=1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "REVIEW_ITEM_NOT_OWNED")

    def test_client_cannot_forge_outcome_via_request_body(self):
        """No field in the request contract accepts outcome/mastery/state — only `answer` (code)."""
        client, user = _active_client("forgeoutcomeuser@example.com")
        module = _module_with_weak_concept(user)
        session = ReviewSessionService.create_session_for_trigger(user, "module_completed", module_id=module.id)
        item = session.items.first()

        url = reverse("review:submit-item", kwargs={"session_id": session.id, "item_id": item.id})
        from unittest.mock import patch

        with patch("apps.review.services.run_exercise_attempt.delay"):
            response = client.post(
                url, {"answer": "x=1", "outcome": "pass", "mastery_state": "mastered"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        # outcome remains null (queued) — forged fields were ignored entirely.
        self.assertIsNone(response.data["data"]["outcome"])

    def test_nonexistent_session_returns_not_owned(self):
        client, user = _active_client("nosessionuser@example.com")
        url = reverse(
            "review:submit-item",
            kwargs={
                "session_id": "00000000-0000-0000-0000-000000000000",
                "item_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        response = client.post(url, {"answer": "x=1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)