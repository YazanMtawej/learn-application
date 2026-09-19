import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Concept",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("base_difficulty", models.PositiveIntegerField()),
            ],
            options={"db_table": "concepts"},
        ),
        migrations.CreateModel(
            name="Module",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("order_index", models.PositiveIntegerField(unique=True)),
            ],
            options={"db_table": "modules", "ordering": ["order_index"]},
        ),
        migrations.CreateModel(
            name="Prerequisite",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("mastery_threshold", models.FloatField(blank=True, null=True)),
                (
                    "source_concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prerequisite_targets",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "target_concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prerequisite_sources",
                        to="learning_content.concept",
                    ),
                ),
            ],
            options={"db_table": "prerequisites"},
        ),
        migrations.CreateModel(
            name="Lesson",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("objective", models.TextField()),
                ("content_ref", models.TextField()),
                ("order_index", models.PositiveIntegerField()),
                (
                    "concept",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lessons",
                        to="learning_content.concept",
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lessons",
                        to="learning_content.module",
                    ),
                ),
            ],
            options={"db_table": "lessons", "ordering": ["module", "order_index"]},
        ),
        migrations.CreateModel(
            name="Exercise",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("code_writing", "Code Writing"),
                            ("debugging", "Debugging"),
                            ("mcq", "MCQ"),
                        ],
                        max_length=20,
                    ),
                ),
                ("difficulty", models.PositiveIntegerField()),
                (
                    "lifecycle_status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("validated", "Validated"),
                            ("published", "Published"),
                            ("archived", "Archived"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exercises",
                        to="learning_content.lesson",
                    ),
                ),
            ],
            options={"db_table": "exercises"},
        ),
        migrations.CreateModel(
            name="ExerciseConcept",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="learning_content.concept"
                    ),
                ),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="learning_content.exercise"
                    ),
                ),
            ],
            options={"db_table": "exercise_concepts"},
        ),
        migrations.AddField(
            model_name="exercise",
            name="concepts",
            field=models.ManyToManyField(
                related_name="exercises",
                through="learning_content.ExerciseConcept",
                to="learning_content.concept",
            ),
        ),
        migrations.CreateModel(
            name="TestCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("input", models.TextField()),
                ("expected_output", models.TextField()),
                (
                    "visibility",
                    models.CharField(
                        choices=[("visible", "Visible"), ("hidden", "Hidden")], max_length=10
                    ),
                ),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="test_cases",
                        to="learning_content.exercise",
                    ),
                ),
            ],
            options={"db_table": "test_cases"},
        ),
        migrations.AddIndex(
            model_name="prerequisite",
            index=models.Index(fields=["target_concept"], name="idx_prereq_target"),
        ),
        migrations.AddConstraint(
            model_name="prerequisite",
            constraint=models.CheckConstraint(
                check=models.Q(("source_concept", models.F("target_concept")), _negated=True),
                name="ck_prereq_source_ne_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="prerequisite",
            constraint=models.UniqueConstraint(
                fields=("source_concept", "target_concept"), name="uq_prereq_source_target"
            ),
        ),
        migrations.AddIndex(
            model_name="lesson",
            index=models.Index(fields=["module"], name="idx_lessons_module"),
        ),
        migrations.AddIndex(
            model_name="exercise",
            index=models.Index(fields=["lesson"], name="idx_exercises_lesson"),
        ),
        migrations.AddIndex(
            model_name="exercise",
            index=models.Index(fields=["lifecycle_status"], name="idx_exercises_status"),
        ),
        migrations.AddConstraint(
            model_name="exercise",
            constraint=models.CheckConstraint(
                check=models.Q(type__in=["code_writing", "debugging", "mcq"]),
                name="ck_exercises_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="exercise",
            constraint=models.CheckConstraint(
                check=models.Q(
                    lifecycle_status__in=["draft", "validated", "published", "archived"]
                ),
                name="ck_exercises_lifecycle_status",
            ),
        ),
        migrations.AddIndex(
            model_name="exerciseconcept",
            index=models.Index(fields=["concept"], name="idx_ec_concept"),
        ),
        migrations.AddConstraint(
            model_name="exerciseconcept",
            constraint=models.UniqueConstraint(
                fields=("exercise", "concept"), name="uq_exercise_concepts"
            ),
        ),
        migrations.AddIndex(
            model_name="testcase",
            index=models.Index(fields=["exercise"], name="idx_testcases_exercise"),
        ),
        migrations.AddConstraint(
            model_name="testcase",
            constraint=models.CheckConstraint(
                check=models.Q(visibility__in=["visible", "hidden"]),
                name="ck_testcases_visibility",
            ),
        ),
    ]