from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdaptiveDecision",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("trigger_event", models.CharField(max_length=50)),
                ("signals_snapshot", models.JSONField()),
                ("recommended_action", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="adaptive_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "adaptive_decisions"},
        ),
        migrations.AddIndex(
            model_name="adaptivedecision",
            index=models.Index(fields=["user", "created_at"], name="idx_ad_user_created"),
        ),
    ]