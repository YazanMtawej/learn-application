from rest_framework import status

from apps.core.error_envelope import AppError


class AttemptNotEvaluatedError(AppError):
    """
    ENGINEERING DECISION (not in Phase 7 §4.5's abbreviated error list,
    same pattern as Task 4's IDEMPOTENCY_KEY_REQUIRED) — a hint cannot
    be generated for an attempt that has not yet produced a Deterministic
    Evaluation Result (Phase 10 §8: Diagnosis/Hint always follows
    evaluation, never precedes it).
    """

    code = "ATTEMPT_NOT_EVALUATED"
    message = "This attempt has not finished evaluation yet."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class HintNotApplicableError(AppError):
    """ENGINEERING DECISION — a passed attempt has no failure to hint about."""

    code = "HINT_NOT_APPLICABLE"
    message = "This attempt already passed; no hint is applicable."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class HintQuotaExceededError(AppError):
    """CONFIRMED code — Phase 7 §4.5 Error Cases."""

    code = "HINT_QUOTA_EXCEEDED"
    message = "You have reached your hint limit for the current period."
    category = "rate_limit"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class InvalidTransitionError(AppError):
    """
    CONFIRMED code — Phase 7 §4.5 Error Cases / Phase 2 §6 "Invalid
    Transition". Also reused (rather than inventing a new code) for the
    case where all 3 documented hint levels are already exhausted:
    Phase 1 §27/FR-AI-004 confirms Solution Reveal beyond Level 3 is
    Post-MVP and gated-off by default, so there is no valid next level
    to transition to — the same rejection semantics apply.
    """

    code = "INVALID_TRANSITION"
    message = "This hint level transition is not allowed."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST