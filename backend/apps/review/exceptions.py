from rest_framework import status

from apps.core.error_envelope import AppError


class ReviewSessionNotOwnedError(AppError):
    """Same anti-enumeration pattern as ATTEMPT_NOT_OWNED (Task 4)."""

    code = "REVIEW_SESSION_NOT_OWNED"
    message = "No review session was found for this request."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ReviewItemNotOwnedError(AppError):
    code = "REVIEW_ITEM_NOT_OWNED"
    message = "No review item was found for this request."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ReviewContentUnavailableError(AppError):
    """
    ENGINEERING DECISION — raised only when a mandatory trigger
    (module_completed/assessment_remediation, Phase 17 §7 Fallback)
    cannot produce even a single published Exercise for any concept in
    scope. Not documented explicitly as an error code in Phase 7
    (REVIEW-START's abbreviated error list is empty); named following
    the project's established `<DOMAIN>_CONTENT_UNAVAILABLE` pattern.
    """

    code = "REVIEW_CONTENT_UNAVAILABLE"
    message = "No published content is currently available for this review."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class ReviewSessionNotActiveError(AppError):
    code = "REVIEW_SESSION_NOT_ACTIVE"
    message = "This review session is not active."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT