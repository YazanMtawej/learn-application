from django.contrib import admin

from apps.content_authoring.models import ContentDraft


@admin.register(ContentDraft)
class ContentDraftAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "content_type", "status", "created_at")
    list_filter = ("content_type", "status")
    readonly_fields = (
        "id", "author", "content_type", "payload", "validation_result",
        "published_lesson", "published_exercise", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False