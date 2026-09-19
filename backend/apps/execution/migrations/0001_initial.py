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
            name="ExerciseAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.TextField()),
                ("attempt_number", models.PositiveIntegerField()),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("idempotency_key", models.CharField(max_length=255, unique=True)),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="learning_content.exercise",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exercise_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "exercise_attempts"},
        ),
        migrations.CreateModel(
            name="Execution",
            fields=[
                (
                    "attempt",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="execution",
                        serialize=False,
                        to="execution.exerciseattempt",
                    ),
                ),
                (
                    "result_type",
                    models.CharField(
                        choices=[
                            ("pass", "Pass"),
                            ("fail", "Fail"),
                            ("timeout", "Timeout"),
                            ("runtime_error", "Runtime Error"),
                            ("system_error", "System Error"),
                            ("cancelled", "Cancelled"),
                        ],
                        max_length=20,
                    ),
                ),
                ("raw_output_ref", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField()),
            ],
            options={"db_table": "executions"},
        ),
        migrations.CreateModel(
            name="EvaluationResult",
            fields=[
                (
                    "attempt",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="evaluation_result",
                        serialize=False,
                        to="execution.exerciseattempt",
                    ),
                ),
                ("outcome", models.CharField(choices=[("pass", "Pass"), ("fail", "Fail")], max_length=10)),
                (
                    "error_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("technical", "Technical"),
                            ("conceptual", "Conceptual"),
                            ("system", "System"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("details_ref", models.TextField(blank=True, null=True)),
            ],
            options={"db_table": "evaluation_results"},
        ),
        migrations.AddIndex(
            model_name="exerciseattempt",
            index=models.Index(fields=["user", "exercise"], name="idx_attempts_user_exercise"),
        ),
        migrations.AddConstraint(
            model_name="execution",
            constraint=models.CheckConstraint(
                check=models.Q(
                    result_type__in=[
                        "pass", "fail", "timeout", "runtime_error", "system_error", "cancelled",
                    ]
                ),
                name="ck_executions_result_type",
            ),
        ),
        migrations.AddIndex(
            model_name="evaluationresult",
            index=models.Index(fields=["outcome"], name="idx_eval_outcome"),
        ),
        migrations.AddConstraint(
            model_name="evaluationresult",
            constraint=models.CheckConstraint(
                check=models.Q(outcome__in=["pass", "fail"]),
                name="ck_evaluation_results_outcome",
            ),
        ),
        migrations.AddConstraint(
            model_name="evaluationresult",
            constraint=models.CheckConstraint(
                check=models.Q(error_type__in=["technical", "conceptual", "system"])
                | models.Q(error_type__isnull=True),
                name="ck_evaluation_results_error_type",
            ),
        ),
    ]