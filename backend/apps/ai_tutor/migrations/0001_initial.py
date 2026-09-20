import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0001_initial"),
        ("execution", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Hint",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("level", models.PositiveSmallIntegerField()),
                ("content", models.TextField()),
                (
                    "policy_check_result",
                    models.CharField(
                        choices=[("approved", "Approved"), ("rejected", "Rejected")], max_length=10
                    ),
                ),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "attempt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="hints",
                        to="execution.exerciseattempt",
                    ),
                ),
            ],
            options={"db_table": "hints"},
        ),
        migrations.CreateModel(
            name="AIInteraction",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("use_case", models.CharField(max_length=50)),
                ("model_version", models.CharField(max_length=100)),
                ("cost", models.FloatField(default=0.0)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                (
                    "policy_result",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("unavailable", "Unavailable"),
                            ("malformed", "Malformed"),
                        ],
                        max_length=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="ai_interactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "ai_interactions"},
        ),
        migrations.AddIndex(
            model_name="hint",
            index=models.Index(fields=["attempt"], name="idx_hints_attempt"),
        ),
        migrations.AddConstraint(
            model_name="hint",
            constraint=models.CheckConstraint(
                check=models.Q(("level__gte", 1)) & models.Q(("level__lte", 3)), name="ck_hints_level"
            ),
        ),
        migrations.AddConstraint(
            model_name="hint",
            constraint=models.CheckConstraint(
                check=models.Q(policy_check_result__in=["approved", "rejected"]),
                name="ck_hints_policy_check_result",
            ),
        ),
        migrations.AddIndex(
            model_name="aiinteraction",
            index=models.Index(fields=["user", "created_at"], name="idx_ai_user_created"),
        ),
    ]