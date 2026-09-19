from django.contrib import admin

from apps.adaptive.models import AdaptiveDecision


@admin.register(AdaptiveDecision)
class AdaptiveDecisionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "trigger_event", "created_at")
    list_filter = ("trigger_event",)
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "user", "trigger_event", "signals_snapshot", "recommended_action", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False