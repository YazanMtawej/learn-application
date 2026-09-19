import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("learning_content", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentDraft",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "content_type",
                    models.CharField(
                        choices=[("lesson", "Lesson"), ("exercise", "Exercise")], max_length=20
                    ),
                ),
                ("payload", models.JSONField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("validated", "Validated"),
                            ("published", "Published"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("validation_result", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="content_drafts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "published_lesson",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_draft",
                        to="learning_content.lesson",
                    ),
                ),
                (
                    "published_exercise",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_draft",
                        to="learning_content.exercise",
                    ),
                ),
            ],
            options={"db_table": "content_drafts"},
        ),
        migrations.AddIndex(
            model_name="contentdraft",
            index=models.Index(fields=["author", "status"], name="idx_cd_author_status"),
        ),
        migrations.AddConstraint(
            model_name="contentdraft",
            constraint=models.CheckConstraint(
                check=models.Q(content_type__in=["lesson", "exercise"]),
                name="ck_content_drafts_content_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentdraft",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["draft", "validated", "published"]),
                name="ck_content_drafts_status",
            ),
        ),
    ]