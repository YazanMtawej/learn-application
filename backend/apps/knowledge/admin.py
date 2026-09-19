from django.contrib import admin

from apps.knowledge.models import ConceptFlawLog, ConceptMastery, Evidence


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "concept", "attempt", "correctness", "hint_usage", "error_type", "created_at")
    list_filter = ("correctness", "error_type")
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "user", "concept", "attempt", "correctness", "hint_usage", "error_type", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ConceptMastery)
class ConceptMasteryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "concept", "updated_at")
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "user", "concept", "mastery_value", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(ConceptFlawLog)
class ConceptFlawLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "concept", "error_type", "occurrence_count", "flagged", "last_detected_at")
    list_filter = ("flagged", "error_type")
    search_fields = ("user__email", "user__phone")
    readonly_fields = (
        "id", "user", "concept", "error_type", "occurrence_count", "flagged",
        "first_detected_at", "last_detected_at",
    )

    def has_add_permission(self, request):
        return False