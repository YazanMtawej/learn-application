from django.db import transaction

from apps.assessment.exceptions import (
    AssessmentAlreadyPassedError,
    AssessmentAttemptNotOwnedError,
    AssessmentNotFoundError,
    AttemptInProgressError,
    AttemptNotActiveError,
    InvalidItemError,
    RemediationRequiredError,
)
from apps.assessment.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentResponse,
    RemediationPath,
)
from apps.execution.services import ExecutionSubmissionService
from apps.execution.tasks import run_exercise_attempt
from apps.review.exceptions import ReviewContentUnavailableError
from apps.review.models import ReviewSession
from apps.review.services import ReviewSessionService


class AssessmentEligibilityService:
    """
    Phase 2 SM-06 attempt-eligibility logic. Deterministic,
    server-authoritative (Phase 16 §28-style Security applied here).
    """

    @classmethod
    def resolve_next_attempt_number(cls, assessment: Assessment, user) -> int:
        attempts = list(
            AssessmentAttempt.objects.filter(assessment=assessment, user=user).order_by("-attempt_number")
        )

        if attempts and attempts[0].result == AssessmentAttempt.Result.IN_PROGRESS:
            raise AttemptInProgressError()

        if any(a.result == AssessmentAttempt.Result.PASSED for a in attempts):
            raise AssessmentAlreadyPassedError()

        count = len(attempts)
        if count < assessment.max_attempts:
            return count + 1

        # Attempts exhausted — Phase 1 §5.9 FR-ASSESS-003 Remediation path.
        latest_failed = attempts[0]
        remediation = cls._resolve_remediation(latest_failed, assessment, user)

        if remediation.status != RemediationPath.Status.COMPLETED:
            raise RemediationRequiredError()

        # Exactly one additional attempt is granted per completed
        # remediation (Phase 2: "محاولة إضافية بعد إتمام Remediation") —
        # not a reset of the counter.
        already_used = AssessmentAttempt.objects.filter(
            assessment=assessment, user=user, attempt_number__gt=count
        ).exists()
        if already_used:
            raise RemediationRequiredError()

        return count + 1

    @classmethod
    @transaction.atomic
    def _resolve_remediation(cls, latest_failed_attempt, assessment, user) -> RemediationPath:
        remediation, created = RemediationPath.objects.get_or_create(
            assessment_attempt=latest_failed_attempt,
            defaults={"status": RemediationPath.Status.REQUIRED},
        )

        if remediation.status == RemediationPath.Status.COMPLETED:
            return remediation

        if created:
            try:
                ReviewSessionService.create_session_for_trigger(
                    user=user, trigger_context="assessment_remediation", module_id=assessment.module_id
                )
            except ReviewContentUnavailableError:
                # Phase 17 §7 Fallback content unavailable — remediation
                # stays 'required'; cannot be auto-completed without
                # content. Documented gap, not silently bypassed.
                pass

        # Completion detection: a completed Review session for this
        # user/module, created after this RemediationPath, satisfies it
        # (Assessment reads Review state — it never writes to Review's
        # tables, preserving ownership per Phase 4 §14).
        qualifying_session = (
            ReviewSession.objects.filter(
                user=user,
                trigger_context="review_prerequisite",  # placeholder narrowed below
            )
        )
        qualifying_session = ReviewSession.objects.filter(
            user=user,
            trigger_context="assessment_remediation",
            status=ReviewSession.Status.COMPLETED,
            created_at__gte=remediation.created_at,
        ).exists()

        if qualifying_session:
            remediation.status = RemediationPath.Status.COMPLETED
            remediation.completed_at = _now()
            remediation.save(update_fields=["status", "completed_at"])

        return remediation


def _now():
    from django.utils import timezone

    return timezone.now()


class AssessmentAttemptService:
    @staticmethod
    def get_assessment_for_module(module_id) -> Assessment:
        try:
            return Assessment.objects.select_related("module").get(module_id=module_id)
        except (Assessment.DoesNotExist, ValueError, TypeError):
            raise AssessmentNotFoundError()

    @classmethod
    @transaction.atomic
    def start_attempt(cls, user, module_id) -> AssessmentAttempt:
        assessment = cls.get_assessment_for_module(module_id)
        next_number = AssessmentEligibilityService.resolve_next_attempt_number(assessment, user)

        attempt = AssessmentAttempt.objects.create(
            assessment=assessment, user=user, attempt_number=next_number,
            result=AssessmentAttempt.Result.IN_PROGRESS,
        )
        return attempt

    @staticmethod
    def get_owned_attempt(user, attempt_id) -> AssessmentAttempt:
        try:
            return AssessmentAttempt.objects.select_related("assessment").get(id=attempt_id, user=user)
        except (AssessmentAttempt.DoesNotExist, ValueError, TypeError):
            raise AssessmentAttemptNotOwnedError()

    @classmethod
    @transaction.atomic
    def submit_answers(cls, user, attempt_id, answers: list, idempotency_prefix: str) -> AssessmentAttempt:
        attempt = cls.get_owned_attempt(user, attempt_id)

        if attempt.result != AssessmentAttempt.Result.IN_PROGRESS:
            raise AttemptNotActiveError()

        item_ids = set(attempt.assessment.items.values_list("id", flat=True))

        for entry in answers:
            item_id = entry["item_id"]
            code = entry["code"]

            if item_id not in item_ids:
                raise InvalidItemError()

            item = attempt.assessment.items.get(id=item_id)
            response, created = AssessmentResponse.objects.get_or_create(attempt=attempt, item=item)

            if response.exercise_attempt_id is not None:
                continue  # Idempotent — already answered, skip.

            exercise_attempt, exercise_attempt_created = ExecutionSubmissionService.submit(
                user=user,
                exercise_id=item.exercise_id,
                code=code,
                idempotency_key=f"{idempotency_prefix}-{item_id}",
            )
            response.exercise_attempt = exercise_attempt
            response.save(update_fields=["exercise_attempt"])

            if exercise_attempt_created:
                transaction.on_commit(lambda ea=exercise_attempt: run_exercise_attempt.delay(str(ea.id)))

        return attempt

    @classmethod
    @transaction.atomic
    def finalize_if_ready(cls, attempt: AssessmentAttempt) -> None:
        """
        Called by the signal handler once every response in the attempt
        has a resolved EvaluationResult. Scoring: ENGINEERING DECISION
        — "all items pass" (no scoring formula documented anywhere for
        Assessment specifically), same class of provisional rule used
        in Task 8.
        """
        responses = list(attempt.responses.select_related("exercise_attempt__evaluation_result"))

        for response in responses:
            if response.exercise_attempt_id is None:
                return  # not all items answered yet
            if not hasattr(response.exercise_attempt, "evaluation_result"):
                return  # still queued/executing (Phase 6 §7.J async)

        all_passed = all(
            r.exercise_attempt.evaluation_result.outcome == "pass" for r in responses
        )
        attempt.result = AssessmentAttempt.Result.PASSED if all_passed else AssessmentAttempt.Result.FAILED
        attempt.save(update_fields=["result"])


class AssessmentReadService:
    @staticmethod
    def get_attempt_status(attempt: AssessmentAttempt) -> dict:
        remediation_required = False
        if attempt.result == AssessmentAttempt.Result.FAILED:
            remediation_path = getattr(attempt, "remediation_path", None)
            remediation_required = (
                remediation_path is not None
                and remediation_path.status != RemediationPath.Status.COMPLETED
            )

        return {
            "attempt_id": attempt.id,
            "result": attempt.result,
            "remediation_required": remediation_required,
        }