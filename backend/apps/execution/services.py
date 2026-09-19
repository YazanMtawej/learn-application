import json

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.execution.exceptions import (
    AttemptNotCancellableError,
    AttemptNotOwnedError,
    ExecutionConcurrencyLimitExceededError,
    ExecutionQuotaExceededError,
    ExerciseNotActiveError,
    ExerciseNotFoundError,
    IdempotencyKeyRequiredError,
)
from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt
from apps.execution.sandbox import build_sandbox_runner
from apps.learning_content.models import Exercise, TestCase
from apps.subscriptions.services import SubscriptionService


class ExecutionSubmissionService:
    """Application-layer submission/status/cancel logic (Phase 6 §5)."""

    @classmethod
    @transaction.atomic
    def submit(cls, user, exercise_id, code: str, idempotency_key: str):
        if not idempotency_key:
            raise IdempotencyKeyRequiredError()

        existing = ExerciseAttempt.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.user_id != user.id:
                raise AttemptNotOwnedError()
            return existing, False

        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except (Exercise.DoesNotExist, ValueError, TypeError):
            raise ExerciseNotFoundError()

        if exercise.lifecycle_status != Exercise.LifecycleStatus.PUBLISHED:
            raise ExerciseNotActiveError()

        cls._enforce_concurrency_limit(user)
        cls._enforce_entitlement_quota(user)

        attempt_number = ExerciseAttempt.objects.filter(user=user, exercise=exercise).count() + 1

        attempt = ExerciseAttempt.objects.create(
            user=user,
            exercise=exercise,
            code=code,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key,
        )
        return attempt, True

    @staticmethod
    def _enforce_concurrency_limit(user):
        from django.conf import settings

        in_flight = ExerciseAttempt.objects.filter(user=user, execution__isnull=True).count()
        if in_flight >= settings.EXECUTION_MAX_CONCURRENT_PER_USER:
            raise ExecutionConcurrencyLimitExceededError()

    @staticmethod
    def _enforce_entitlement_quota(user):
        """
        Enforced only if a matching Entitlement row exists (Task 2:
        no entitlement numeric values were seeded — Phase 1 §16/Phase 10
        P10-D15 leave these TBD). Absence of a configured entitlement
        means no product-level quota is currently active — a documented
        ENGINEERING DECISION, not an invented limit.
        """
        entitlement = SubscriptionService.has_entitlement(user, "executions_per_day")
        if entitlement is None or entitlement.limit_value is None:
            return

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = ExerciseAttempt.objects.filter(
            user=user, submitted_at__gte=today_start
        ).count()
        if today_count >= entitlement.limit_value:
            raise ExecutionQuotaExceededError()

    @staticmethod
    def get_owned_attempt(user, attempt_id) -> ExerciseAttempt:
        try:
            return ExerciseAttempt.objects.select_related("exercise").get(id=attempt_id, user=user)
        except (ExerciseAttempt.DoesNotExist, ValueError, TypeError):
            raise AttemptNotOwnedError()

    @classmethod
    def cancel(cls, user, attempt_id) -> ExerciseAttempt:
        attempt = cls.get_owned_attempt(user, attempt_id)

        if Execution.objects.filter(attempt=attempt).exists():
            raise AttemptNotCancellableError()

        try:
            with transaction.atomic():
                Execution.objects.create(
                    attempt=attempt,
                    result_type=Execution.ResultType.CANCELLED,
                    raw_output_ref="cancelled_by_user",
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )
        except IntegrityError:
            # Lost the race with the running worker task reaching
            # ResultCaptured first (Phase 9 ADR-9.4) — already terminal.
            raise AttemptNotCancellableError()

        return attempt


class ExecutionRunnerService:
    """
    Celery-task-invoked execution orchestration (Phase 6 §7.H: Django
    process never executes student code directly — this runs inside the
    Celery worker process, which invokes the sandbox subprocess).
    """

    @classmethod
    def run_attempt(cls, attempt_id) -> None:
        try:
            attempt = ExerciseAttempt.objects.select_related("exercise").get(id=attempt_id)
        except ExerciseAttempt.DoesNotExist:
            return

        # Phase 9 ADR-9.4: no retry once a terminal result exists
        # (covers both prior completion and user cancellation).
        if Execution.objects.filter(attempt=attempt).exists():
            return

        test_cases = list(
            TestCase.objects.filter(exercise=attempt.exercise).order_by("id")
        )
        runner = build_sandbox_runner()
        started_at = timezone.now()

        per_test_results = []
        for test_case in test_cases:
            # Cooperative cancellation checkpoint between test cases.
            if Execution.objects.filter(attempt=attempt).exists():
                return

            result = runner.run(attempt.code, test_case.input)

            if result.timed_out:
                cls._finalize(attempt, Execution.ResultType.TIMEOUT, "timeout", started_at)
                return
            if result.system_error:
                cls._finalize(
                    attempt, Execution.ResultType.SYSTEM_ERROR, "sandbox_failure", started_at
                )
                return

            per_test_results.append((test_case, result))

        cls._evaluate_and_finalize(attempt, started_at, per_test_results)

    @staticmethod
    def _finalize(attempt, result_type, raw_output_ref, started_at):
        Execution.objects.get_or_create(
            attempt=attempt,
            defaults={
                "result_type": result_type,
                "raw_output_ref": raw_output_ref,
                "started_at": started_at,
                "completed_at": timezone.now(),
            },
        )

    @classmethod
    def _evaluate_and_finalize(cls, attempt, started_at, per_test_results):
        """
        Deterministic evaluation, performed entirely in the trusted
        worker process — never inside the sandboxed subprocess (Phase 9
        §10: "Evaluation... خارج الـSandbox، داخل الـWorker").
        """
        any_runtime_error = False
        all_passed = True
        details = []

        for test_case, result in per_test_results:
            passed = result.exit_code == 0 and result.stdout.strip() == test_case.expected_output.strip()
            if result.exit_code != 0:
                any_runtime_error = True
            if not passed:
                all_passed = False

            details.append(
                {
                    "test_case_id": str(test_case.id),
                    "visibility": test_case.visibility,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "passed": passed,
                    "truncated": result.truncated,
                }
            )

        if any_runtime_error:
            result_type = Execution.ResultType.RUNTIME_ERROR
            outcome = EvaluationResult.Outcome.FAIL
            error_type = EvaluationResult.ErrorType.TECHNICAL
        elif all_passed:
            result_type = Execution.ResultType.PASS
            outcome = EvaluationResult.Outcome.PASS
            error_type = None
        else:
            result_type = Execution.ResultType.FAIL
            outcome = EvaluationResult.Outcome.FAIL
            # Technical-vs-conceptual classification requires the
            # Concept Flaw Log / AI diagnosis machinery — Phase 4 §7,
            # Phase 10 §3 — explicitly out of TASK 4 scope. Left NULL
            # per the Phase 8 §4.4 CHECK constraint ("OR error_type IS
            # NULL"), not guessed here.
            error_type = None

        raw_output_ref = json.dumps(details)

        with transaction.atomic():
            execution, created = Execution.objects.get_or_create(
                attempt=attempt,
                defaults={
                    "result_type": result_type,
                    "raw_output_ref": raw_output_ref,
                    "started_at": started_at,
                    "completed_at": timezone.now(),
                },
            )
            if created:
                EvaluationResult.objects.create(
                    attempt=attempt,
                    outcome=outcome,
                    error_type=error_type,
                    details_ref=raw_output_ref,
                )