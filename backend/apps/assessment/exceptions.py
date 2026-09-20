from rest_framework import status

from apps.core.error_envelope import AppError


class AssessmentNotFoundError(AppError):
    code = "ASSESSMENT_NOT_FOUND"
    message = "The requested assessment does not exist."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class AssessmentAttemptNotOwnedError(AppError):
    code = "ASSESSMENT_ATTEMPT_NOT_OWNED"
    message = "No assessment attempt was found for this request."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class AttemptInProgressError(AppError):
    """ENGINEERING DECISION — prevents concurrent attempts for the same assessment."""

    code = "ATTEMPT_IN_PROGRESS"
    message = "You already have an in-progress attempt for this assessment."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class AssessmentAlreadyPassedError(AppError):
    """DERIVED — no documented rule for retaking a passed Module Assessment."""

    code = "ASSESSMENT_ALREADY_PASSED"
    message = "You have already passed this assessment."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class RemediationRequiredError(AppError):
    """
    CONFIRMED behavior — Phase 1 §5.9 FR-ASSESS-003 / Phase 2 §26:
    never a permanent block, always a documented path forward.
    """

    code = "REMEDIATION_REQUIRED"
    message = "You must complete the required remediation review before attempting again."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class InvalidItemError(AppError):
    code = "INVALID_ASSESSMENT_ITEM"
    message = "This item does not belong to the assessment being attempted."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST


class AttemptNotActiveError(AppError):
    code = "ASSESSMENT_ATTEMPT_NOT_ACTIVE"
    message = "This assessment attempt is not in progress."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT