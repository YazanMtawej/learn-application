import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("email", models.EmailField(blank=True, max_length=254, null=True, unique=True)),
                ("phone", models.CharField(blank=True, max_length=32, null=True, unique=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("student", "Student"),
                            ("instructor", "Instructor"),
                            ("organization", "Organization"),
                            ("admin", "Admin"),
                        ],
                        default="student",
                        max_length=20,
                    ),
                ),
                (
                    "verification_status",
                    models.CharField(
                        choices=[("unverified", "Unverified"), ("verified", "Verified")],
                        default="unverified",
                        max_length=20,
                    ),
                ),
                (
                    "account_status",
                    models.CharField(
                        choices=[
                            ("unverified", "Unverified"),
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                        ],
                        default="unverified",
                        max_length=20,
                    ),
                ),
                ("is_staff", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "users",
            },
        ),
        migrations.CreateModel(
            name="RefreshToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(max_length=128, unique=True)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked", models.BooleanField(default=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refresh_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "refresh_tokens",
            },
        ),
        migrations.CreateModel(
            name="VerificationCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code_hash", models.CharField(max_length=128)),
                (
                    "purpose",
                    models.CharField(
                        choices=[("registration", "Registration")],
                        default="registration",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "verification_codes",
            },
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="idx_users_email"),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["phone"], name="idx_users_phone"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=models.Q(role__in=["student", "instructor", "organization", "admin"]),
                name="ck_users_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=models.Q(account_status__in=["unverified", "active", "suspended"]),
                name="ck_users_account_status",
            ),
        ),
        migrations.AddIndex(
            model_name="refreshtoken",
            index=models.Index(fields=["user"], name="idx_refresh_user"),
        ),
        migrations.AddIndex(
            model_name="verificationcode",
            index=models.Index(fields=["user", "purpose"], name="idx_verifcode_user_purpose"),
        ),
    ]