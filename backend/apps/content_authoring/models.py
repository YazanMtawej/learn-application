import uuid

from django.conf import settings
from django.db import models

from apps.learning_content.models import Exercise, Lesson


class ContentDraft(models.Model):
    """
    CONFIRMED — Phase 8 §4.11 `content_drafts` table, verbatim
    (author_id, content_type, payload jsonb, status, validation_result).

    published_lesson / published_exercise: NOT in Phase 8 §4.11's field
    list. Added as nullable traceability FKs so a draft can be linked to
    the concrete Lesson/Exercise row it produces on publish
    (ENGINEERING DECISION — low-risk, non-business-affecting, needed
    because Phase 8 documents no other way to answer "what did this
    draft become?"; never exposed as a required/invented business rule).
    """

    class ContentType(models.TextChoices):
        LESSON = "lesson", "Lesson"
        EXERCISE = "exercise", "Exercise"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="content_drafts",
    )

    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
    )

    payload = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    validation_result = models.TextField(
        null=True,
        blank=True,
    )

    published_lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_draft",
    )

    published_exercise = models.ForeignKey(
        Exercise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_draft",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "content_drafts"

        indexes = [
            models.Index(
                fields=["author", "status"],
                name="idx_cd_author_status",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    content_type__in=[
                        "lesson",
                        "exercise",
                    ]
                ),
                name="ck_content_drafts_content_type",
            ),
            models.CheckConstraint(
                check=models.Q(
                    status__in=[
                        "draft",
                        "validated",
                        "published",
                    ]
                ),
                name="ck_content_drafts_status",
            ),
        ]

    def __str__(self):
        return (
            f"ContentDraft({self.id}) "
            f"type={self.content_type} "
            f"status={self.status}"
        )