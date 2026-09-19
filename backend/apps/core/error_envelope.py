import logging
import uuid

from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class AppError(Exception):
    """
    Base class for application/domain-level errors that map directly to the
    unified error envelope defined in PHASE_7_API_SERVICE_CONTRACTS.md §8.
    """

    code = "SYSTEM_ERROR"
    message = "An unexpected error occurred."
    category = "system"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message=None, code=None, category=None, status_code=None):
        self.message = message or self.message
        self.code = code or self.code
        self.category = category or self.category
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


def _build_envelope(code, message, category, correlation_id=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "category": category,
            "correlation_id": correlation_id or str(uuid.uuid4()),
        }
    }


def _category_for_drf_exception(exc):
    if isinstance(exc, drf_exceptions.Throttled):
        return "rate_limit"

    if isinstance(
        exc,
        (
            drf_exceptions.NotAuthenticated,
            drf_exceptions.AuthenticationFailed,
        ),
    ):
        return "authorization"

    if isinstance(exc, drf_exceptions.PermissionDenied):
        return "authorization"

    if isinstance(exc, drf_exceptions.NotFound):
        return "not_found"

    if isinstance(exc, drf_exceptions.ValidationError):
        return "validation"

    return "system"


def _flatten_validation_message(detail):
    if isinstance(detail, dict):
        parts = []

        for field, errs in detail.items():
            if isinstance(errs, (list, tuple)):
                for error in errs:
                    parts.append(f"{field}: {error}")
            else:
                parts.append(f"{field}: {errs}")

        return "; ".join(parts) if parts else "Invalid input."

    if isinstance(detail, (list, tuple)):
        return "; ".join(str(error) for error in detail)

    return str(detail)


def custom_exception_handler(exc, context):
    correlation_id = str(uuid.uuid4())

    if isinstance(exc, AppError):
        logger.warning(
            "AppError raised: code=%s category=%s correlation_id=%s",
            exc.code,
            exc.category,
            correlation_id,
        )

        return Response(
            _build_envelope(
                exc.code,
                exc.message,
                exc.category,
                correlation_id,
            ),
            status=exc.status_code,
        )

    # Import lazily to avoid circular import during Django/DRF startup.
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)

    if response is not None:
        category = _category_for_drf_exception(exc)

        if category == "validation":
            message = _flatten_validation_message(response.data)
            code = "VALIDATION_ERROR"

        elif isinstance(exc, drf_exceptions.NotAuthenticated):
            message = "Authentication credentials were not provided."
            code = "NOT_AUTHENTICATED"

        elif isinstance(exc, drf_exceptions.AuthenticationFailed):
            message = "Invalid or expired authentication credentials."
            code = "AUTHENTICATION_FAILED"

        elif isinstance(exc, drf_exceptions.PermissionDenied):
            message = "You do not have permission to perform this action."
            code = "PERMISSION_DENIED"

        elif isinstance(exc, drf_exceptions.NotFound):
            message = "The requested resource was not found."
            code = "NOT_FOUND"

        elif isinstance(exc, drf_exceptions.Throttled):
            message = "Too many requests. Please try again later."
            code = "RATE_LIMITED"

        else:
            message = "A request error occurred."
            code = "REQUEST_ERROR"

        logger.warning(
            "DRF exception handled: code=%s category=%s correlation_id=%s",
            code,
            category,
            correlation_id,
        )

        return Response(
            _build_envelope(
                code,
                message,
                category,
                correlation_id,
            ),
            status=response.status_code,
        )

    logger.error(
        "Unhandled exception: correlation_id=%s",
        correlation_id,
        exc_info=True,
    )

    return Response(
        _build_envelope(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred. Please try again later.",
            "system",
            correlation_id,
        ),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )