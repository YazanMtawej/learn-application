import uuid

from django.db import migrations

SEED_PLANS = [
    ("free", "Free"),
    ("pro", "Pro"),
    ("student", "Student"),
    ("organization", "Organization"),
]


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    for code, name in SEED_PLANS:
        Plan.objects.get_or_create(code=code, defaults={"id": uuid.uuid4(), "name": name})


def remove_seeded_plans(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.filter(code__in=[code for code, _ in SEED_PLANS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, remove_seeded_plans),
    ]