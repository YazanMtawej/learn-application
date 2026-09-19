from rest_framework import status

from apps.core.error_envelope import AppError


class IdempotencyKeyRequiredError(AppError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    message = "An Idempotency-Key header is required for this request."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST


class ExerciseNotFoundError(AppError):
    code = "EXERCISE_NOT_FOUND"
    message = "The requested exercise does not exist."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ExerciseNotActiveError(AppError):
    """CONFIRMED code — Phase 7 §4.4 Error Cases."""

    code = "EXERCISE_NOT_ACTIVE"
    message = "This exercise is not currently active."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class AttemptNotOwnedError(AppError):
    """
    CONFIRMED code — Phase 7 §4.4 Error Cases. Category/status follow
    Phase 7 §8's anti-enumeration rule ("نفس الكود لمنع تسريب وجود مورد
    لغير المالك") — used identically whether the attempt truly does not
    exist or belongs to another user.
    """

    code = "ATTEMPT_NOT_OWNED"
    message = "No attempt was found for this request."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ExecutionQuotaExceededError(AppError):
    """CONFIRMED code — Phase 7 §4.4 Error Cases."""

    code = "EXECUTION_QUOTA_EXCEEDED"
    message = "You have reached your execution limit for the current period."
    category = "rate_limit"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class ExecutionConcurrencyLimitExceededError(AppError):
    """
    ENGINEERING DECISION — Phase 9 §7/§12 documents a per-user
    concurrency limit (value=2) as a security control, distinct from
    the product/commercial EXECUTION_QUOTA_EXCEEDED entitlement above
    (Phase 9 §15: "Subscription/Entitlement Limits هي طبقة منتجية
    تجارية منفصلة تمامًا عن Security Controls").
    """

    code = "EXECUTION_CONCURRENCY_LIMIT_EXCEEDED"
    message = "You have too many executions in progress. Please wait for one to finish."
    category = "rate_limit"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class AttemptNotCancellableError(AppError):
    code = "ATTEMPT_NOT_CANCELLABLE"
    message = "This attempt has already reached a final state and cannot be cancelled."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT