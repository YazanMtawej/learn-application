import uuid

from django.db import IntegrityError
from django.test import TestCase

from apps.learning_content.models import (
    Concept,
    Exercise,
    ExerciseConcept,
    Lesson,
    Module,
    Prerequisite,
    TestCase as TestCaseModel,
)


class ConceptModelTests(TestCase):
    def test_name_uniqueness_enforced(self):
        Concept.objects.create(id=uuid.uuid4(), name="Loops", base_difficulty=2)
        with self.assertRaises(IntegrityError):
            Concept.objects.create(id=uuid.uuid4(), name="Loops", base_difficulty=3)


class PrerequisiteModelTests(TestCase):
    def setUp(self):
        self.variables = Concept.objects.create(id=uuid.uuid4(), name="Variables", base_difficulty=1)
        self.loops = Concept.objects.create(id=uuid.uuid4(), name="Loops", base_difficulty=2)

    def test_source_cannot_equal_target(self):
        with self.assertRaises(IntegrityError):
            Prerequisite.objects.create(source_concept=self.variables, target_concept=self.variables)

    def test_duplicate_edge_rejected(self):
        Prerequisite.objects.create(source_concept=self.variables, target_concept=self.loops)
        with self.assertRaises(IntegrityError):
            Prerequisite.objects.create(source_concept=self.variables, target_concept=self.loops)

    def test_mastery_threshold_nullable(self):
        prereq = Prerequisite.objects.create(source_concept=self.variables, target_concept=self.loops)
        self.assertIsNone(prereq.mastery_threshold)


class ModuleModelTests(TestCase):
    def test_order_index_uniqueness_enforced(self):
        Module.objects.create(id=uuid.uuid4(), title="Fundamentals", order_index=1)
        with self.assertRaises(IntegrityError):
            Module.objects.create(id=uuid.uuid4(), title="Other", order_index=1)


class LessonModelTests(TestCase):
    def setUp(self):
        self.module = Module.objects.create(id=uuid.uuid4(), title="Fundamentals", order_index=1)

    def test_lesson_requires_module(self):
        with self.assertRaises(IntegrityError):
            Lesson.objects.create(
                module_id=None, objective="Learn variables", content_ref="ref://1", order_index=1
            )

    def test_lesson_concept_optional(self):
        lesson = Lesson.objects.create(
            module=self.module, objective="Intro", content_ref="ref://intro", order_index=1
        )
        self.assertIsNone(lesson.concept)


class ExerciseModelTests(TestCase):
    def setUp(self):
        self.module = Module.objects.create(id=uuid.uuid4(), title="Fundamentals", order_index=1)
        self.lesson = Lesson.objects.create(
            module=self.module, objective="Intro", content_ref="ref://1", order_index=1
        )
        self.concept = Concept.objects.create(id=uuid.uuid4(), name="Variables", base_difficulty=1)

    def test_invalid_type_rejected_by_constraint(self):
        exercise = Exercise.objects.create(lesson=self.lesson, type="mcq", difficulty=1)
        exercise.type = "not_a_real_type"
        with self.assertRaises(IntegrityError):
            exercise.save()

    def test_invalid_lifecycle_status_rejected_by_constraint(self):
        exercise = Exercise.objects.create(lesson=self.lesson, type="mcq", difficulty=1)
        exercise.lifecycle_status = "not_a_real_status"
        with self.assertRaises(IntegrityError):
            exercise.save()

    def test_default_lifecycle_status_is_draft(self):
        exercise = Exercise.objects.create(lesson=self.lesson, type="mcq", difficulty=1)
        self.assertEqual(exercise.lifecycle_status, "draft")

    def test_exercise_concept_uniqueness_enforced(self):
        exercise = Exercise.objects.create(lesson=self.lesson, type="mcq", difficulty=1)
        ExerciseConcept.objects.create(exercise=exercise, concept=self.concept)
        with self.assertRaises(IntegrityError):
            ExerciseConcept.objects.create(exercise=exercise, concept=self.concept)


class TestCaseModelTests(TestCase):
    def setUp(self):
        module = Module.objects.create(id=uuid.uuid4(), title="Fundamentals", order_index=1)
        lesson = Lesson.objects.create(
            module=module, objective="Intro", content_ref="ref://1", order_index=1
        )
        self.exercise = Exercise.objects.create(lesson=lesson, type="code_writing", difficulty=1)

    def test_invalid_visibility_rejected_by_constraint(self):
        tc = TestCaseModel.objects.create(
            exercise=self.exercise, input="1", expected_output="1", visibility="visible"
        )
        tc.visibility = "not_a_real_visibility"
        with self.assertRaises(IntegrityError):
            tc.save()