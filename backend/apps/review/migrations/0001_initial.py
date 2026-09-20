import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("learning_content", "0001_initial"),
        ("execution", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "trigger_context",
                    models.CharField(
                        choices=[
                            ("module_completed", "Module Completed"),
                            ("assessment_remediation", "Assessment Remediation"),
                            ("review_concept", "Review Concept"),
                            ("review_prerequisite", "Review Prerequisite"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("remediation", "Remediation"),
                        ],
                        default="pending",
                        max_length=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="review_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "review_sessions"},
        ),
        migrations.CreateModel(
            name="ReviewItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "outcome",
                    models.CharField(
                        blank=True,
                        choices=[("pass", "Pass"), ("fail", "Fail")],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "attempt",
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="review_item",
                        to="execution.exerciseattempt",
                    ),
                ),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="review_items",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "question_ref",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="review_items",
                        to="learning_content.exercise",
                    ),
                ),
                (
                    "review_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="review.reviewsession",
                    ),
                ),
            ],
            options={"db_table": "review_items"},
        ),
        migrations.AddIndex(
            model_name="reviewsession",
            index=models.Index(fields=["user"], name="idx_rs_user"),
        ),
        migrations.AddConstraint(
            model_name="reviewsession",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["pending", "active", "completed", "remediation"]),
                name="ck_review_sessions_status",
            ),
        ),
        migrations.AddIndex(
            model_name="reviewitem",
            index=models.Index(fields=["review_session"], name="idx_ri_session"),
        ),
        migrations.AddConstraint(
            model_name="reviewitem",
            constraint=models.CheckConstraint(
                check=models.Q(outcome__in=["pass", "fail"]) | models.Q(outcome__isnull=True),
                name="ck_review_items_outcome",
            ),
        ),
    ]