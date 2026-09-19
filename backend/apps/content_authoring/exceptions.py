from rest_framework import status

from apps.core.error_envelope import AppError


class ContentDraftNotFoundError(AppError):
    code = "CONTENT_DRAFT_NOT_FOUND"
    message = "The requested content draft does not exist."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class DraftAlreadyPublishedError(AppError):
    code = "DRAFT_ALREADY_PUBLISHED"
    message = "This content draft has already been published."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class ValidationFailedError(AppError):
    """
    CONFIRMED error code — Phase 7 §4.10: "CONTENT-PUBLISH يفشل بـ
    VALIDATION_FAILED إن لم يجتز التمرين/الدرس فحص Deterministic
    Validation".
    """

    code = "VALIDATION_FAILED"
    message = "This content did not pass deterministic validation."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST