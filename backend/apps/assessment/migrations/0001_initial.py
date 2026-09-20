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
            name="Assessment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("max_attempts", models.PositiveIntegerField()),
                (
                    "module",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="assessment",
                        to="learning_content.module",
                    ),
                ),
            ],
            options={"db_table": "assessments"},
        ),
        migrations.CreateModel(
            name="AssessmentItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("order_index", models.PositiveIntegerField()),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="assessment.assessment",
                    ),
                ),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="assessment_items",
                        to="learning_content.exercise",
                    ),
                ),
            ],
            options={"db_table": "assessment_items", "ordering": ["order_index"]},
        ),
        migrations.CreateModel(
            name="AssessmentAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("attempt_number", models.PositiveIntegerField()),
                (
                    "result",
                    models.CharField(
                        choices=[
                            ("in_progress", "In Progress"),
                            ("passed", "Passed"),
                            ("failed", "Failed"),
                        ],
                        default="in_progress",
                        max_length=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="attempts",
                        to="assessment.assessment",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="assessment_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "assessment_attempts"},
        ),
        migrations.CreateModel(
            name="AssessmentResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "attempt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="assessment.assessmentattempt",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="responses",
                        to="assessment.assessmentitem",
                    ),
                ),
                (
                    "exercise_attempt",
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="assessment_response",
                        to="execution.exerciseattempt",
                    ),
                ),
            ],
            options={"db_table": "assessment_responses"},
        ),
        migrations.CreateModel(
            name="RemediationPath",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("required", "Required"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                        ],
                        default="required",
                        max_length=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assessment_attempt",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remediation_path",
                        to="assessment.assessmentattempt",
                    ),
                ),
            ],
            options={"db_table": "remediation_paths"},
        ),
        migrations.AddConstraint(
            model_name="assessmentitem",
            constraint=models.UniqueConstraint(
                fields=("assessment", "exercise"), name="uq_assessment_item_exercise"
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentitem",
            constraint=models.UniqueConstraint(
                fields=("assessment", "order_index"), name="uq_assessment_item_order"
            ),
        ),
        migrations.AddIndex(
            model_name="assessmentattempt",
            index=models.Index(fields=["user"], name="idx_aa_user"),
        ),
        migrations.AddConstraint(
            model_name="assessmentattempt",
            constraint=models.CheckConstraint(
                check=models.Q(result__in=["in_progress", "passed", "failed"]),
                name="ck_assessment_attempts_result",
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentattempt",
            constraint=models.UniqueConstraint(
                fields=("assessment", "user", "attempt_number"), name="uq_aa_assessment_user_number"
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentresponse",
            constraint=models.UniqueConstraint(
                fields=("attempt", "item"), name="uq_assessment_response_attempt_item"
            ),
        ),
        migrations.AddConstraint(
            model_name="remediationpath",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["required", "in_progress", "completed"]),
                name="ck_remediation_paths_status",
            ),
        ),
    ]