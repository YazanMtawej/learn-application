from django.contrib import admin

from apps.identity.models import RefreshToken, User, VerificationCode


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "phone",
        "role",
        "verification_status",
        "account_status",
        "is_staff",
        "created_at",
    )
    list_filter = ("role", "verification_status", "account_status", "is_staff")
    search_fields = ("email", "phone", "id")
    readonly_fields = ("id", "created_at", "updated_at", "password")
    ordering = ("-created_at",)


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "issued_at", "expires_at", "revoked")
    list_filter = ("revoked",)
    readonly_fields = ("id", "user", "token_hash", "issued_at", "expires_at", "revoked")
    search_fields = ("user__email", "user__phone")

    def has_add_permission(self, request):
        return False


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "purpose", "expires_at", "consumed_at", "attempts")
    readonly_fields = (
        "id", "user", "code_hash", "purpose", "expires_at",
        "consumed_at", "attempts", "created_at",
    )
    search_fields = ("user__email", "user__phone")

    def has_add_permission(self, request):
        return False