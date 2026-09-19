from django.test import TestCase

from apps.adaptive import actions
from apps.adaptive.candidates import CandidateGenerator
from apps.adaptive.context import ConceptState


def _state(mastery_state="developing"):
    return ConceptState(
        concept_id="c1", mastery_state=mastery_state, mastery_score=0.5,
        active_flaw=False, review_recommended=False, last_evidence_at=None,
    )


class CandidateGenerationTests(TestCase):
    def test_module_completed_generates_unlock_assessment_and_mandatory_review(self):
        candidates = CandidateGenerator.generate("module_completed", "c1", _state(), active_flaw=False)
        types = {c.action_type for c in candidates}
        self.assertIn(actions.UNLOCK_ASSESSMENT, types)
        self.assertIn(actions.REVIEW_CONCEPT, types)

    def test_insufficient_evidence_never_generates_review_candidate(self):
        candidates = CandidateGenerator.generate(
            "submission_passed", "c1", _state(mastery_state="insufficient_evidence"), active_flaw=False
        )
        types = {c.action_type for c in candidates}
        self.assertNotIn(actions.REVIEW_CONCEPT, types)
        self.assertNotIn(actions.REVIEW_PREREQUISITE, types)
        self.assertIn(actions.CONTINUE, types)

    def test_active_flaw_generates_review_candidate(self):
        candidates = CandidateGenerator.generate("submission_failed", "c1", _state(), active_flaw=True)
        types = {c.action_type for c in candidates}
        self.assertIn(actions.REVIEW_CONCEPT, types)

    def test_isolated_failure_without_flaw_generates_explanation_not_review(self):
        candidates = CandidateGenerator.generate("submission_failed", "c1", _state(), active_flaw=False)
        types = {c.action_type for c in candidates}
        self.assertIn(actions.TRIGGER_EXPLANATION, types)
        self.assertNotIn(actions.REVIEW_CONCEPT, types)

    def test_strong_success_generates_harder_practice(self):
        candidates = CandidateGenerator.generate(
            "submission_passed", "c1", _state(mastery_state="mastered"), active_flaw=False
        )
        types = {c.action_type for c in candidates}
        self.assertIn(actions.PRACTICE_HARDER, types)

    def test_continue_always_present_as_fallback_candidate(self):
        candidates = CandidateGenerator.generate("submission_passed", "c1", _state(), active_flaw=False)
        types = {c.action_type for c in candidates}
        self.assertIn(actions.CONTINUE, types)