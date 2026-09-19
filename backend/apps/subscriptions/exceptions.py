from rest_framework import status

from apps.core.error_envelope import AppError


class PlanNotFoundError(AppError):
    code = "PLAN_NOT_FOUND"
    message = "The requested plan does not exist."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class SubscriptionNotFoundError(AppError):
    code = "SUBSCRIPTION_NOT_FOUND"
    message = "No subscription was found for this account."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class SubscriptionNotCancellableError(AppError):
    code = "SUBSCRIPTION_NOT_CANCELLABLE"
    message = "This subscription is not in a cancellable state."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class InvalidWebhookSignatureError(AppError):
    code = "INVALID_WEBHOOK_SIGNATURE"
    message = "The webhook signature is invalid or missing."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED


class WebhookPayloadInvalidError(AppError):
    code = "WEBHOOK_PAYLOAD_INVALID"
    message = "The webhook payload is missing required fields."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST


class WebhookSubscriptionNotFoundError(AppError):
    code = "WEBHOOK_SUBSCRIPTION_NOT_FOUND"
    message = "The subscription referenced by this webhook event does not exist."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND