from django.contrib import admin

from apps.ai_tutor.models import AIInteraction, Hint


@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "level", "policy_check_result", "delivered_at")
    list_filter = ("policy_check_result", "level")
    readonly_fields = ("id", "attempt", "level", "content", "policy_check_result", "delivered_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "use_case", "model_version", "policy_result", "latency_ms", "created_at")
    list_filter = ("use_case", "policy_result")
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "user", "use_case", "model_version", "cost", "latency_ms", "policy_result", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False