from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.adaptive.services import AdaptiveDecisionService
from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module


def _active_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


class AdaptiveAPISecurityTests(TestCase):
    def setUp(self):
        module = Module.objects.create(title="Fundamentals", order_index=1)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(
            lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published"
        )
        self.concept = Concept.objects.create(name="Variables", base_difficulty=1)
        ExerciseConcept.objects.create(exercise=exercise, concept=self.concept)
        self.url = reverse("adaptive:current")

    def test_unauthenticated_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_write_endpoint_exists_for_current_path(self):
        client, _ = _active_client("nowriteuser@example.com")
        response = client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_only_sees_own_decision(self):
        client_a, user_a = _active_client("adaptivea@example.com")
        client_b, user_b = _active_client("adaptiveb@example.com")

        AdaptiveDecisionService.decide(user_a, "submission_passed", str(self.concept.id))

        response_b = client_b.get(self.url)
        self.assertIsNone(response_b.data["data"]["recommended_action"])

        response_a = client_a.get(self.url)
        self.assertIsNotNone(response_a.data["data"]["recommended_action"])

    def test_response_never_exposes_full_signals_snapshot(self):
        client, user = _active_client("snapshotuser@example.com")
        AdaptiveDecisionService.decide(user, "submission_passed", str(self.concept.id))
        response = client.get(self.url)
        self.assertNotIn("signals_snapshot", response.data["data"])
        self.assertNotIn("concept_states", response.data["data"])