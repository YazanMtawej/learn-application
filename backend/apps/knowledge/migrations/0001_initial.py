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
            name="Evidence",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("correctness", models.BooleanField()),
                ("hint_usage", models.PositiveSmallIntegerField(default=0)),
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "attempt",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="evidence_records",
                        to="execution.exerciseattempt",
                    ),
                ),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="evidence_records",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="evidence_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "evidence"},
        ),
        migrations.CreateModel(
            name="ConceptMastery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("mastery_value", models.JSONField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="masteries",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="concept_masteries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "concept_mastery"},
        ),
        migrations.CreateModel(
            name="ConceptFlawLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "error_type",
                    models.CharField(
                        choices=[
                            ("technical", "Technical"),
                            ("conceptual", "Conceptual"),
                            ("system", "System"),
                        ],
                        max_length=20,
                    ),
                ),
                ("occurrence_count", models.PositiveIntegerField(default=0)),
                ("flagged", models.BooleanField(default=False)),
                ("first_detected_at", models.DateTimeField(auto_now_add=True)),
                ("last_detected_at", models.DateTimeField(auto_now=True)),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="flaw_logs",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="concept_flaws",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "concept_flaw_log"},
        ),
        migrations.AddIndex(
            model_name="evidence",
            index=models.Index(fields=["user", "concept"], name="idx_evidence_user_concept"),
        ),
        migrations.AddIndex(
            model_name="evidence",
            index=models.Index(fields=["created_at"], name="idx_evidence_created_at"),
        ),
        migrations.AddConstraint(
            model_name="evidence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("attempt__isnull", False)),
                fields=("attempt", "concept"),
                name="uq_evidence_attempt_concept",
            ),
        ),
        migrations.AddIndex(
            model_name="conceptmastery",
            index=models.Index(fields=["user"], name="idx_cm_user"),
        ),
        migrations.AddConstraint(
            model_name="conceptmastery",
            constraint=models.UniqueConstraint(
                fields=("user", "concept"), name="uq_concept_mastery_user_concept"
            ),
        ),
        migrations.AddIndex(
            model_name="conceptflawlog",
            index=models.Index(fields=["flagged"], name="idx_flaw_flagged"),
        ),
        migrations.AddConstraint(
            model_name="conceptflawlog",
            constraint=models.UniqueConstraint(
                fields=("user", "concept", "error_type"), name="uq_flaw_user_concept_errortype"
            ),
        ),
    ]