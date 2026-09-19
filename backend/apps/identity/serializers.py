from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.identity.models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=False)
    phone = serializers.CharField(required=False, allow_blank=False, max_length=32)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError(
                "Either 'email' or 'phone' must be provided."
            )
        return attrs

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class VerifySerializer(serializers.Serializer):
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