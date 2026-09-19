from django.test import TestCase

from apps.adaptive import actions
from apps.adaptive.candidates import Candidate
from apps.adaptive.conflict_resolution import ConflictResolver
from apps.adaptive.priority import PriorityLadder


class PriorityLadderTests(TestCase):
    def test_active_flaw_ranks_above_default(self):
        flaw_candidate = Candidate(actions.REVIEW_CONCEPT, target_concept_id="c1", rationale_tag="active_flaw")
        default_candidate = Candidate(actions.CONTINUE, target_concept_id="c1")
        ranked = PriorityLadder.rank([default_candidate, flaw_candidate])
        self.assertEqual(ranked[0], flaw_candidate)

    def test_mandatory_module_review_ranks_above_milestone(self):
        review = Candidate(actions.REVIEW_CONCEPT, target_concept_id="c1", rationale_tag="mandatory_module_review")
        unlock = Candidate(actions.UNLOCK_ASSESSMENT, target_concept_id="c1")
        ranked = PriorityLadder.rank([unlock, review])
        self.assertEqual(ranked[0], review)


class ConflictResolutionTests(TestCase):
    def test_review_prerequisite_beats_review_concept_on_tie(self):
        review_concept = Candidate(actions.REVIEW_CONCEPT, target_concept_id="c1")
        review_prereq = Candidate(actions.REVIEW_PREREQUISITE, target_concept_id="p1")
        # Force both into the same rung by tagging identically.
        review_concept.rationale_tag = ""
        review_prereq.rationale_tag = ""
        resolved = ConflictResolver.resolve([review_prereq, review_concept])
        self.assertEqual(resolved.action_type, actions.REVIEW_PREREQUISITE)

    def test_mandatory_review_beats_unlock_assessment(self):
        review = Candidate(actions.REVIEW_CONCEPT, target_concept_id="c1", rationale_tag="mandatory_module_review")
        unlock = Candidate(actions.UNLOCK_ASSESSMENT, target_concept_id="c1")
        resolved = ConflictResolver.resolve([review, unlock])
        self.assertEqual(resolved.action_type, actions.REVIEW_CONCEPT)

    def test_empty_candidate_list_returns_none(self):
        self.assertIsNone(ConflictResolver.resolve([]))