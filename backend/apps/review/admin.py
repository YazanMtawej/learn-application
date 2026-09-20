from django.contrib import admin

from apps.review.models import ReviewItem, ReviewSession


class ReviewItemInline(admin.TabularInline):
    model = ReviewItem
    extra = 0
    readonly_fields = ("id", "concept", "question_ref", "attempt", "outcome")
    can_delete = False


@admin.register(ReviewSession)
class ReviewSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "trigger_context", "status", "created_at")
    list_filter = ("trigger_context", "status")
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "user", "trigger_context", "status", "created_at")
    inlines = [ReviewItemInline]

    def has_add_permission(self, request):
        return False