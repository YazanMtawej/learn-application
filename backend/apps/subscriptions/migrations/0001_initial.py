import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("free", "Free"),
                            ("pro", "Pro"),
                            ("student", "Student"),
                            ("organization", "Organization"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
            options={
                "db_table": "plans",
            },
        ),
        migrations.CreateModel(
            name="Entitlement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("feature_key", models.CharField(max_length=100)),
                ("limit_value", models.IntegerField(blank=True, null=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="entitlements",
                        to="subscriptions.plan",
                    ),
                ),
            ],
            options={
                "db_table": "entitlements",
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("trial", "Trial"),
                            ("active", "Active"),
                            ("past_due", "Past Due"),
                            ("grace", "Grace"),
                            ("expired", "Expired"),
                            ("cancelled", "Cancelled"),
                        ],
                        max_length=20,
                    ),
                ),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("grace_period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="subscriptions.plan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "subscriptions",
            },
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_event_id", models.CharField(max_length=255, unique=True)),
                ("type", models.CharField(max_length=50)),
                ("payload_ref", models.TextField()),
                ("processed_at", models.DateTimeField()),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_events",
                        to="subscriptions.subscription",
                    ),
                ),
            ],
            options={
                "db_table": "payment_events",
            },
        ),
        migrations.AddConstraint(
            model_name="plan",
            constraint=models.CheckConstraint(
                check=models.Q(code__in=["free", "pro", "student", "organization"]),
                name="ck_plans_code",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlement",
            index=models.Index(fields=["plan"], name="idx_ent_plan"),
        ),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.UniqueConstraint(
                fields=("plan", "feature_key"), name="uq_entitlements_plan_feature"
            ),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["user"], name="idx_sub_user"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["status"], name="idx_sub_status"),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(
                check=models.Q(
                    status__in=["trial", "active", "past_due", "grace", "expired", "cancelled"]
                ),
                name="ck_subscriptions_status",
            ),
        ),
        migrations.AddIndex(
            model_name="paymentevent",
            index=models.Index(fields=["subscription"], name="idx_pe_subscription"),
        ),
    ]