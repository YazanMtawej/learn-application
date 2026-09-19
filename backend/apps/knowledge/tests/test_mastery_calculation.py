from django.test import TestCase, override_settings

from apps.identity.models import User
from apps.knowledge.mastery_states import (
    DEVELOPING,
    INSUFFICIENT_EVIDENCE,
    MASTERED,
    NOT_ASSESSED,
    PROFICIENT,
)
from apps.knowledge.models import ConceptFlawLog, Evidence
from apps.knowledge.services import MasteryCalculationService
from apps.learning_content.models import Concept


TEST_SETTINGS = dict(
    MASTERY_WINDOW_SIZE=6,
    MASTERY_MIN_EVIDENCE_FOR_SUFFICIENCY=3,
    MASTERY_MIN_CORRECTNESS_FOR_PROFICIENT=0.6,
    MASTERY_MIN_CORRECTNESS_FOR_MASTERED=0.85,
    MASTERY_MIN_STRONG_RATIO_FOR_MASTERED=0.75,
)


@override_settings(**TEST_SETTINGS)
class MasteryStateTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="masteryuser@example.com", password="StrongPass123!")
        self.concept = Concept.objects.create(name="Recursion", base_difficulty=3)

    def _add_evidence(self, correctness, hint_usage=0, error_type=None):
        return Evidence.objects.create(
            user=self.user, concept=self.concept, correctness=correctness,
            hint_usage=hint_usage, error_type=error_type,
        )

    def test_no_evidence_yields_not_assessed(self):
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertEqual(mastery.mastery_value["state"], NOT_ASSESSED)

    def test_single_evidence_yields_insufficient_evidence(self):
        self._add_evidence(correctness=True)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertEqual(mastery.mastery_value["state"], INSUFFICIENT_EVIDENCE)

    def test_insufficient_cannot_jump_directly_to_proficient(self):
        # Even with a single strong pass, it must not skip to Proficient/Mastered.
        self._add_evidence(correctness=True)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertIn(mastery.mastery_value["state"], {NOT_ASSESSED, INSUFFICIENT_EVIDENCE, DEVELOPING})

    def test_sufficient_consistent_success_reaches_developing_or_higher(self):
        for _ in range(3):
            self._add_evidence(correctness=True)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertIn(mastery.mastery_value["state"], {DEVELOPING, PROFICIENT})

    def test_strong_consistent_evidence_reaches_mastered(self):
        for _ in range(6):
            self._add_evidence(correctness=True, hint_usage=0)
        # Recalculate progressively to respect one-step-at-a-time promotion.
        for _ in range(4):
            MasteryCalculationService.recalculate(self.user, self.concept)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertEqual(mastery.mastery_value["state"], MASTERED)

    def test_single_transient_failure_does_not_immediately_demote_from_mastered(self):
        for _ in range(6):
            self._add_evidence(correctness=True, hint_usage=0)
        for _ in range(5):
            mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertEqual(mastery.mastery_value["state"], MASTERED)

        self._add_evidence(correctness=False, error_type=Evidence.ErrorType.TECHNICAL)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        # One transient failure must regress by at most one step.
        self.assertIn(mastery.mastery_value["state"], {MASTERED, PROFICIENT})

    def test_active_conceptual_flaw_blocks_mastered(self):
        for _ in range(6):
            self._add_evidence(correctness=True, hint_usage=0)
        for _ in range(4):
            MasteryCalculationService.recalculate(self.user, self.concept)

        ConceptFlawLog.objects.create(
            user=self.user, concept=self.concept, error_type=Evidence.ErrorType.CONCEPTUAL,
            occurrence_count=5, flagged=True,
        )
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertNotEqual(mastery.mastery_value["state"], MASTERED)
        self.assertEqual(mastery.mastery_value["state"], PROFICIENT)

    def test_hint_heavy_success_does_not_count_as_strong_evidence(self):
        for _ in range(6):
            self._add_evidence(correctness=True, hint_usage=3)
        for _ in range(4):
            mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        # High hint usage should prevent reaching Mastered via strong_ratio gate.
        self.assertNotEqual(mastery.mastery_value["state"], MASTERED)

    def test_mastery_score_is_within_bounds(self):
        for _ in range(5):
            self._add_evidence(correctness=True)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertGreaterEqual(mastery.mastery_value["score"], 0.0)
        self.assertLessEqual(mastery.mastery_value["score"], 1.0)

    def test_reason_and_algorithm_version_present(self):
        self._add_evidence(correctness=True)
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertTrue(mastery.mastery_value["reason"])
        self.assertTrue(mastery.mastery_value["algorithm_version"])

    def test_review_recommended_true_on_regression(self):
        for _ in range(6):
            self._add_evidence(correctness=True, hint_usage=0)
        for _ in range(4):
            MasteryCalculationService.recalculate(self.user, self.concept)

        ConceptFlawLog.objects.create(
            user=self.user, concept=self.concept, error_type=Evidence.ErrorType.CONCEPTUAL,
            occurrence_count=5, flagged=True,
        )
        mastery = MasteryCalculationService.recalculate(self.user, self.concept)
        self.assertTrue(mastery.mastery_value["review_recommended"])