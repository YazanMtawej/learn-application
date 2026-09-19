from django.test import TestCase

from apps.adaptive.candidates import Candidate
from apps.adaptive.context import ConceptState, StudentAdaptiveContext
from apps.adaptive.eligibility import EligibilityFilter
from apps.learning_content.models import Concept, Exercise, Lesson, Module


class PrerequisiteGateFilterTests(TestCase):
    def _context(self, prereq_entries):
        return StudentAdaptiveContext(
            user_id="u1", concept_states={}, prerequisite_map={"c1": prereq_entries},
            ai_concept_signal=None,
        )

    def test_unsatisfied_prerequisite_blocks_candidate(self):
        candidate = Candidate(action_type="CONTINUE", target_concept_id="c1")
        result = EligibilityFilter.check_prerequisite_gate(candidate, self._context([("p1", False)]))
        self.assertFalse(result.eligible)

    def test_satisfied_prerequisite_allows_candidate(self):
        candidate = Candidate(action_type="CONTINUE", target_concept_id="c1")
        result = EligibilityFilter.check_prerequisite_gate(candidate, self._context([("p1", True)]))
        self.assertTrue(result.eligible)

    def test_fail_open_on_unknown_prerequisite_state(self):
        """Phase 16 §7: technical read failure (None) must NOT block."""
        candidate = Candidate(action_type="CONTINUE", target_concept_id="c1")
        result = EligibilityFilter.check_prerequisite_gate(candidate, self._context([("p1", None)]))
        self.assertTrue(result.eligible)

    def test_no_target_concept_always_eligible(self):
        candidate = Candidate(action_type="STAY", target_concept_id=None)
        result = EligibilityFilter.check_prerequisite_gate(candidate, self._context([]))
        self.assertTrue(result.eligible)


class ContentAvailabilityFilterTests(TestCase):
    def setUp(self):
        module = Module.objects.create(title="Fundamentals", order_index=1)
        self.lesson = Lesson.objects.create(module=module, objective="x", content_ref="r", order_index=1)
        self.concept = Concept.objects.create(name="Loops", base_difficulty=1)

    def test_unpublished_content_blocks_candidate(self):
        exercise = Exercise.objects.create(lesson=self.lesson, type="mcq", difficulty=1)
        exercise.concepts.add(self.concept)
        candidate = Candidate(action_type="CONTINUE", target_concept_id=str(self.concept.id))
        result = EligibilityFilter.check_content_availability(candidate)
        self.assertFalse(result.eligible)

    def test_published_content_allows_candidate(self):
        exercise = Exercise.objects.create(
            lesson=self.lesson, type="mcq", difficulty=1, lifecycle_status="published"
        )
        exercise.concepts.add(self.concept)
        candidate = Candidate(action_type="CONTINUE", target_concept_id=str(self.concept.id))
        result = EligibilityFilter.check_content_availability(candidate)
        self.assertTrue(result.eligible)


class MasterySufficiencyFilterTests(TestCase):
    def test_practice_harder_blocked_when_mastery_insufficient(self):
        context = StudentAdaptiveContext(
            user_id="u1",
            concept_states={"c1": ConceptState("c1", "insufficient_evidence", 0.1, False, False, None)},
            prerequisite_map={},
            ai_concept_signal=None,
        )
        candidate = Candidate(action_type="PRACTICE_HARDER", target_concept_id="c1")
        result = EligibilityFilter.check_mastery_sufficiency(candidate, context)
        self.assertFalse(result.eligible)

    def test_practice_harder_allowed_when_mastery_developing(self):
        context = StudentAdaptiveContext(
            user_id="u1",
            concept_states={"c1": ConceptState("c1", "developing", 0.5, False, False, None)},
            prerequisite_map={},
            ai_concept_signal=None,
        )
        candidate = Candidate(action_type="PRACTICE_HARDER", target_concept_id="c1")
        result = EligibilityFilter.check_mastery_sufficiency(candidate, context)
        self.assertTrue(result.eligible)


class RemediationStateFilterTests(TestCase):
    def test_unlock_assessment_blocked_during_remediation(self):
        candidate = Candidate(action_type="UNLOCK_ASSESSMENT", target_concept_id="c1")
        result = EligibilityFilter.check_remediation_state(candidate, remediation_pending=True)
        self.assertFalse(result.eligible)

    def test_unlock_assessment_allowed_without_remediation(self):
        candidate = Candidate(action_type="UNLOCK_ASSESSMENT", target_concept_id="c1")
        result = EligibilityFilter.check_remediation_state(candidate, remediation_pending=False)
        self.assertTrue(result.eligible)