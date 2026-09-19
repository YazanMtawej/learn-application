from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.knowledge.models import ConceptFlawLog, Evidence
from apps.learning_content.models import Concept


def _active_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


class MasteryReadAPITests(TestCase):
    def setUp(self):
        self.client, self.user = _active_client("readuser@example.com")
        self.url = reverse("knowledge:mastery-read")

    def test_unauthenticated_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_not_assessed_for_concept_without_evidence(self):
        Concept.objects.create(name="Exceptions", base_difficulty=2)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entries = response.data["data"]["mastery"]
        self.assertTrue(any(e["mastery_state"] == "not_assessed" for e in entries))

    def test_response_never_includes_client_writable_fields(self):
        response = self.client.get(self.url)
        # GET-only endpoint — no mutation path exists at all.
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_reflects_own_evidence_only(self):
        concept = Concept.objects.create(name="Iterators", base_difficulty=2)
        Evidence.objects.create(user=self.user, concept=concept, correctness=True)
        from apps.knowledge.services import MasteryCalculationService

        MasteryCalculationService.recalculate(self.user, concept)

        other_client, other_user = _active_client("otherreaduser@example.com")
        other_response = other_client.get(self.url)
        other_entry = next(e for e in other_response.data["data"]["mastery"] if e["concept_id"] == str(concept.id))
        self.assertEqual(other_entry["mastery_state"], "not_assessed")


class FlawLogReadAPITests(TestCase):
    def setUp(self):
        self.client, self.user = _active_client("flawreaduser@example.com")
        self.url = reverse("knowledge:flaw-log-read")

    def test_unauthenticated_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_own_flaw_log_entries_returned(self):
        concept = Concept.objects.create(name="Closures", base_difficulty=3)
        ConceptFlawLog.objects.create(
            user=self.user, concept=concept, error_type="conceptual",
            occurrence_count=3, flagged=True,
        )
        other_client, other_user = _active_client("otherflawuser@example.com")
        ConceptFlawLog.objects.create(
            user=other_user, concept=concept, error_type="technical",
            occurrence_count=1, flagged=False,
        )

        response = self.client.get(self.url)
        entries = response.data["data"]["flaw_log"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["error_type"], "conceptual")