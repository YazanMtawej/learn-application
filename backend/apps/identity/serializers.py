from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.identity.models import User


class RegisterSerializer(serializers.Serializer):
    """
    Request shape CONFIRMED against Phase 7 §4.1 AUTH-REGISTER:
    "identifier (email/phone) + password" — a single unified field.
    """

    identifier = serializers.CharField(required=True, allow_blank=False, max_length=254)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class VerifySerializer(serializers.Serializer):
    """
    UNCONFIRMED IMPLEMENTATION — OWNER DECISION G2. Phase 7 §4.1
    documents AUTH-VERIFY as Auth: "None (verification token)",
    Request: "code" only. The verification-credential mechanism itself
    is not fully specified in any Phase document. Per explicit owner
    decision, `user_id` is retained in the request body as the accepted
    minimal resolution to this gap — not a documented Phase 7 contract
    field, and not to be extended (no verification_token, no JWT, no
    additional schema).
    """

    user_id = serializers.UUIDField()
    code = serializers.CharField(max_length=16)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "role",
            "verification_status",
            "account_status",
        ]
        read_only_fields = fields