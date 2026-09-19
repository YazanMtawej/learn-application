from django.test import TestCase, override_settings

from apps.identity.models import User
from apps.knowledge.models import ConceptFlawLog, Evidence
from apps.knowledge.services import ConceptFlawLogService
from apps.learning_content.models import Concept


@override_settings(CONCEPT_FLAW_OCCURRENCE_THRESHOLD=3)
class ConceptFlawLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="flawuser@example.com", password="StrongPass123!")
        self.concept = Concept.objects.create(name="Scope", base_difficulty=2)

    def _failing_evidence(self, error_type=Evidence.ErrorType.CONCEPTUAL):
        return Evidence.objects.create(
            user=self.user, concept=self.concept, correctness=False, error_type=error_type
        )

    def test_successful_evidence_does_not_create_flaw_log(self):
        evidence = Evidence.objects.create(user=self.user, concept=self.concept, correctness=True)
        ConceptFlawLogService.record_if_applicable(evidence)
        self.assertFalse(ConceptFlawLog.objects.filter(user=self.user, concept=self.concept).exists())

    def test_failure_without_error_type_does_not_create_flaw_log(self):
        evidence = Evidence.objects.create(user=self.user, concept=self.concept, correctness=False)
        ConceptFlawLogService.record_if_applicable(evidence)
        self.assertFalse(ConceptFlawLog.objects.filter(user=self.user, concept=self.concept).exists())

    def test_flaw_not_flagged_below_threshold(self):
        for _ in range(2):
            ConceptFlawLogService.record_if_applicable(self._failing_evidence())
        flaw = ConceptFlawLog.objects.get(user=self.user, concept=self.concept)
        self.assertFalse(flaw.flagged)
        self.assertEqual(flaw.occurrence_count, 2)

    def test_flaw_flagged_at_threshold(self):
        for _ in range(3):
            ConceptFlawLogService.record_if_applicable(self._failing_evidence())
        flaw = ConceptFlawLog.objects.get(user=self.user, concept=self.concept)
        self.assertTrue(flaw.flagged)

    def test_technical_and_conceptual_errors_tracked_separately(self):
        ConceptFlawLogService.record_if_applicable(
            self._failing_evidence(error_type=Evidence.ErrorType.TECHNICAL)
        )
        ConceptFlawLogService.record_if_applicable(
            self._failing_evidence(error_type=Evidence.ErrorType.CONCEPTUAL)
        )
        self.assertEqual(ConceptFlawLog.objects.filter(user=self.user, concept=self.concept).count(), 2)

    def test_has_active_flaw_reflects_flagged_state(self):
        from apps.knowledge.services import ConceptFlawLogService as SVC

        self.assertFalse(SVC.has_active_flaw(self.user, self.concept))
        for _ in range(3):
            SVC.record_if_applicable(self._failing_evidence())
        self.assertTrue(SVC.has_active_flaw(self.user, self.concept))