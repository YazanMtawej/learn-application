from django.test import TestCase

from apps.identity.models import User
from apps.knowledge.models import ConceptFlawLog, Evidence
from apps.knowledge.services import MasteryCalculationService
from apps.learning_content.models import Concept, Exercise, ExerciseConcept, Lesson, Module
from apps.review.candidates import ReviewCandidateService


class CandidateSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="candidateuser@example.com", password="StrongPass123!")
        self.module = Module.objects.create(title="Fundamentals", order_index=1)
        self.lesson = Lesson.objects.create(module=self.module, objective="x", content_ref="ref", order_index=1)

    def _exercise_for(self, concept, published=True):
        exercise = Exercise.objects.create(
            lesson=self.lesson, type="mcq", difficulty=1,
            lifecycle_status="published" if published else "draft",
        )
        ExerciseConcept.objects.create(exercise=exercise, concept=concept)
        return exercise

    def test_concept_with_active_flaw_is_weak(self):
        concept = Concept.objects.create(name="Loops", base_difficulty=1)
        ConceptFlawLog.objects.create(
            user=self.user, concept=concept, error_type="conceptual", occurrence_count=5, flagged=True
        )
        self.assertTrue(ReviewCandidateService.is_weak(self.user, concept))

    def test_concept_with_developing_mastery_is_weak(self):
        concept = Concept.objects.create(name="Recursion", base_difficulty=2)
        for _ in range(3):
            Evidence.objects.create(user=self.user, concept=concept, correctness=True, hint_usage=2)
        MasteryCalculationService.recalculate(self.user, concept)
        self.assertTrue(ReviewCandidateService.is_weak(self.user, concept))

    def test_concept_with_no_evidence_is_not_weak(self):
        concept = Concept.objects.create(name="Scope", base_difficulty=1)
        self.assertFalse(ReviewCandidateService.is_weak(self.user, concept))

    def test_mandatory_trigger_falls_back_to_all_concepts_when_none_weak(self):
        concept = Concept.objects.create(name="Functions", base_difficulty=1)
        result = ReviewCandidateService.select_target_concepts(self.user, "module_completed", [concept])
        self.assertEqual(result, [concept])

    def test_adaptive_trigger_returns_empty_when_none_weak(self):
        concept = Concept.objects.create(name="Exceptions", base_difficulty=1)
        result = ReviewCandidateService.select_target_concepts(self.user, "review_concept", [concept])
        self.assertEqual(result, [])

    def test_item_exercise_selection_skips_unpublished(self):
        concept = Concept.objects.create(name="Iterators", base_difficulty=1)
        self._exercise_for(concept, published=False)
        self.assertIsNone(ReviewCandidateService.select_item_exercise(concept))

    def test_item_exercise_selection_returns_published(self):
        concept = Concept.objects.create(name="Closures", base_difficulty=1)
        exercise = self._exercise_for(concept, published=True)
        self.assertEqual(ReviewCandidateService.select_item_exercise(concept), exercise)