from django.contrib import admin

from apps.execution.models import EvaluationResult, Execution, ExerciseAttempt


@admin.register(ExerciseAttempt)
class ExerciseAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "exercise", "attempt_number", "submitted_at")
    list_filter = ("exercise",)
    search_fields = ("user__email", "user__phone", "idempotency_key")
    readonly_fields = ("id", "user", "exercise", "code", "attempt_number", "submitted_at", "idempotency_key")

    def has_add_permission(self, request):
        return False


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ("attempt", "result_type", "started_at", "completed_at")
    list_filter = ("result_type",)
    readonly_fields = ("attempt", "result_type", "raw_output_ref", "started_at", "completed_at")

    def has_add_permission(self, request):
        return False


@admin.register(EvaluationResult)
class EvaluationResultAdmin(admin.ModelAdmin):
    list_display = ("attempt", "outcome", "error_type")
    list_filter = ("outcome", "error_type")
    readonly_fields = ("attempt", "outcome", "error_type", "details_ref")

    def has_add_permission(self, request):
        return False