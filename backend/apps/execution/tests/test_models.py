import uuid

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.identity.models import User
from apps.learning_content.models import Exercise, Lesson, Module


class ExerciseAttemptModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="attemptuser@example.com", password="StrongPass123!")
        module = Module.objects.create(title="Fundamentals", order_index=1)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        self.exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)

    def test_idempotency_key_uniqueness_enforced(self):
        ExerciseAttempt.objects.create(
            user=self.user, exercise=self.exercise, code="x=1", attempt_number=1,
            idempotency_key="key-1",
        )
        with self.assertRaises(IntegrityError):
            ExerciseAttempt.objects.create(
                user=self.user, exercise=self.exercise, code="x=2", attempt_number=2,
                idempotency_key="key-1",
            )

    def test_multiple_attempts_per_user_exercise_allowed(self):
        ExerciseAttempt.objects.create(
            user=self.user, exercise=self.exercise, code="x=1", attempt_number=1, idempotency_key="a"
        )
        ExerciseAttempt.objects.create(
            user=self.user, exercise=self.exercise, code="x=2", attempt_number=2, idempotency_key="b"
        )
        self.assertEqual(ExerciseAttempt.objects.filter(user=self.user).count(), 2)


class ExecutionModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="execmodeluser@example.com", password="StrongPass123!")
        module = Module.objects.create(title="Fundamentals", order_index=2)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)
        self.attempt = ExerciseAttempt.objects.create(
            user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key="ek"
        )

    def test_invalid_result_type_rejected_by_constraint(self):
        execution = Execution.objects.create(
            attempt=self.attempt, result_type="pass",
            started_at=timezone.now(), completed_at=timezone.now(),
        )
        execution.result_type = "not_a_real_type"
        with self.assertRaises(IntegrityError):
            execution.save()

    def test_one_execution_per_attempt_enforced_by_pk(self):
        Execution.objects.create(
            attempt=self.attempt, result_type="pass",
            started_at=timezone.now(), completed_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            Execution.objects.create(
                attempt=self.attempt, result_type="fail",
                started_at=timezone.now(), completed_at=timezone.now(),
            )


class EvaluationResultModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="evalmodeluser@example.com", password="StrongPass123!")
        module = Module.objects.create(title="Fundamentals", order_index=3)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)
        self.attempt = ExerciseAttempt.objects.create(
            user=user, exercise=exercise, code="x=1", attempt_number=1, idempotency_key="ek2"
        )

    def test_error_type_nullable(self):
        result = EvaluationResult.objects.create(attempt=self.attempt, outcome="pass")
        self.assertIsNone(result.error_type)

    def test_invalid_outcome_rejected_by_constraint(self):
        result = EvaluationResult.objects.create(attempt=self.attempt, outcome="pass")
        result.outcome = "not_a_real_outcome"
        with self.assertRaises(IntegrityError):
            result.save()