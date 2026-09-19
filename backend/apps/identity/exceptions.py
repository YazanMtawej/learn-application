from rest_framework import status

from apps.core.error_envelope import AppError


class IdentifierTakenError(AppError):
    code = "IDENTIFIER_TAKEN"
    message = "This email or phone number is already registered."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    message = "The identifier or password provided is incorrect."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED


class AccountSuspendedError(AppError):
    code = "ACCOUNT_SUSPENDED"
    message = "This account has been suspended."
    category = "authorization"
    status_code = status.HTTP_403_FORBIDDEN


class VerificationCodeExpiredError(AppError):
    code = "VERIFICATION_CODE_EXPIRED"
    message = "This verification code has expired. Please request a new one."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST


class VerificationCodeInvalidError(AppError):
    code = "VERIFICATION_CODE_INVALID"
    message = "This verification code is invalid."
    category = "validation"
    status_code = status.HTTP_400_BAD_REQUEST


class AlreadyVerifiedError(AppError):
    code = "ALREADY_VERIFIED"
    message = "This account has already been verified."
    category = "conflict"
    status_code = status.HTTP_409_CONFLICT


class UserNotFoundError(AppError):
    code = "USER_NOT_FOUND"
    message = "No account was found for this request."
    category = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class RefreshTokenInvalidError(AppError):
    code = "REFRESH_TOKEN_INVALID"
    message = "The refresh token is invalid."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED


class RefreshTokenExpiredError(AppError):
    code = "REFRESH_TOKEN_EXPIRED"
    message = "The refresh token has expired. Please log in again."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED


class RefreshTokenRevokedError(AppError):
    code = "REFRESH_TOKEN_REVOKED"
    message = "This refresh token has already been used or revoked."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED


class AccessTokenInvalidError(AppError):
    code = "ACCESS_TOKEN_INVALID"
    message = "The access token is invalid or has expired."
    category = "authorization"
    status_code = status.HTTP_401_UNAUTHORIZED