from django.contrib import admin

from apps.assessment.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentItem,
    AssessmentResponse,
    RemediationPath,
)


class AssessmentItemInline(admin.TabularInline):
    model = AssessmentItem
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "module", "max_attempts")
    inlines = [AssessmentItemInline]


class AssessmentResponseInline(admin.TabularInline):
    model = AssessmentResponse
    extra = 0
    readonly_fields = ("id", "item", "exercise_attempt")
    can_delete = False


class RemediationPathInline(admin.StackedInline):
    model = RemediationPath
    extra = 0
    readonly_fields = ("id", "status", "created_at", "completed_at")
    can_delete = False


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "assessment", "attempt_number", "result", "created_at")
    list_filter = ("result",)
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "assessment", "user", "attempt_number", "result", "created_at")
    inlines = [AssessmentResponseInline, RemediationPathInline]

    def has_add_permission(self, request):
        return False