from django.db import IntegrityError
from django.test import TestCase

from apps.assessment.models import Assessment, AssessmentAttempt, AssessmentItem
from apps.identity.models import User
from apps.learning_content.models import Exercise, Lesson, Module


def _make_module_and_exercise():
    module = Module.objects.create(title="Fundamentals", order_index=1)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1, lifecycle_status="published")
    return module, exercise


class AssessmentModelTests(TestCase):
    def test_one_assessment_per_module_enforced(self):
        module, _ = _make_module_and_exercise()
        Assessment.objects.create(module=module, max_attempts=2)
        with self.assertRaises(IntegrityError):
            Assessment.objects.create(module=module, max_attempts=3)


class AssessmentItemModelTests(TestCase):
    def setUp(self):
        self.module, self.exercise = _make_module_and_exercise()
        self.assessment = Assessment.objects.create(module=self.module, max_attempts=2)

    def test_duplicate_exercise_in_same_assessment_rejected(self):
        AssessmentItem.objects.create(assessment=self.assessment, exercise=self.exercise, order_index=1)
        other_exercise = Exercise.objects.create(
            lesson=self.exercise.lesson, type="mcq", difficulty=1, lifecycle_status="published"
        )
        with self.assertRaises(IntegrityError):
            AssessmentItem.objects.create(assessment=self.assessment, exercise=self.exercise, order_index=2)
        # Order-index collision also rejected:
        with self.assertRaises(IntegrityError):
            AssessmentItem.objects.create(assessment=self.assessment, exercise=other_exercise, order_index=1)


class AssessmentAttemptModelTests(TestCase):
    def test_attempt_number_uniqueness_enforced(self):
        module, exercise = _make_module_and_exercise()
        assessment = Assessment.objects.create(module=module, max_attempts=2)
        user = User.objects.create_user(email="attemptmodeluser@example.com", password="StrongPass123!")
        AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1)
        with self.assertRaises(IntegrityError):
            AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1)

    def test_invalid_result_rejected_by_constraint(self):
        module, exercise = _make_module_and_exercise()
        assessment = Assessment.objects.create(module=module, max_attempts=2)
        user = User.objects.create_user(email="resultmodeluser@example.com", password="StrongPass123!")
        attempt = AssessmentAttempt.objects.create(assessment=assessment, user=user, attempt_number=1)
        attempt.result = "not_a_real_result"
        with self.assertRaises(IntegrityError):
            attempt.save()