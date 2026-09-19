import uuid

from django.db import models


class Concept(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `concepts` table, verbatim.

    base_difficulty: type/range not documented anywhere in Phase 0-17;
    stored as an unconstrained PositiveIntegerField (ENGINEERING
    DECISION — same low-risk pattern used for numeric fields left
    undocumented elsewhere in the schema).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=200,
        unique=True,
    )

    base_difficulty = models.PositiveIntegerField()

    class Meta:
        db_table = "concepts"

    def __str__(self):
        return self.name


class Prerequisite(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `prerequisites` table, verbatim.

    mastery_threshold: explicitly "TBD — Phase 15" per Phase 8 —
    left nullable with no default; NOT invented here.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    source_concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="prerequisite_targets",
    )

    target_concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name="prerequisite_sources",
    )

    mastery_threshold = models.FloatField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "prerequisites"

        indexes = [
            models.Index(
                fields=["target_concept"],
                name="idx_prereq_target",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=~models.Q(
                    source_concept=models.F("target_concept")
                ),
                name="ck_prereq_source_ne_target",
            ),
            models.UniqueConstraint(
                fields=["source_concept", "target_concept"],
                name="uq_prereq_source_target",
            ),
        ]

    def __str__(self):
        return f"{self.source_concept_id} -> {self.target_concept_id}"


class Module(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `modules` table, verbatim.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(
        max_length=200,
    )

    order_index = models.PositiveIntegerField(
        unique=True,
    )

    class Meta:
        db_table = "modules"
        ordering = ["order_index"]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `lessons` table, verbatim.

    concept_id: Phase 8 states "NOT NULL(module_id)" only for this
    table's constraints — concept_id is left nullable, matching the
    documented constraint exactly (not extended beyond it).

    objective/content_ref: type not documented; stored as TextField
    (ENGINEERING DECISION, low-risk, non-business-affecting).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons",
    )

    concept = models.ForeignKey(
        Concept,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )

    objective = models.TextField()

    content_ref = models.TextField()

    order_index = models.PositiveIntegerField()

    class Meta:
        db_table = "lessons"

        indexes = [
            models.Index(
                fields=["module"],
                name="idx_lessons_module",
            ),
        ]

        ordering = ["module", "order_index"]

    def __str__(self):
        return f"Lesson({self.id}) module={self.module_id}"


class Exercise(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `exercises` table, verbatim, including
    the MVP-scoped type CHECK (Phase 3 §5.4: Code Writing/Debugging/MCQ
    only) and lifecycle_status CHECK.
    """

    class ExerciseType(models.TextChoices):
        CODE_WRITING = "code_writing", "Code Writing"
        DEBUGGING = "debugging", "Debugging"
        MCQ = "mcq", "MCQ"

    class LifecycleStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="exercises",
    )

    type = models.CharField(
        max_length=20,
        choices=ExerciseType.choices,
    )

    difficulty = models.PositiveIntegerField()

    lifecycle_status = models.CharField(
        max_length=20,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.DRAFT,
    )

    concepts = models.ManyToManyField(
        Concept,
        through="ExerciseConcept",
        related_name="exercises",
    )

    class Meta:
        db_table = "exercises"

        indexes = [
            models.Index(
                fields=["lesson"],
                name="idx_exercises_lesson",
            ),
            models.Index(
                fields=["lifecycle_status"],
                name="idx_exercises_status",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    type__in=[
                        "code_writing",
                        "debugging",
                        "mcq",
                    ]
                ),
                name="ck_exercises_type",
            ),
            models.CheckConstraint(
                check=models.Q(
                    lifecycle_status__in=[
                        "draft",
                        "validated",
                        "published",
                        "archived",
                    ]
                ),
                name="ck_exercises_lifecycle_status",
            ),
        ]

    def __str__(self):
        return (
            f"Exercise({self.id}) "
            f"type={self.type} "
            f"status={self.lifecycle_status}"
        )


class ExerciseConcept(models.Model):
    """
    CONFIRMED relationship — Phase 8 §4.2 `exercise_concepts` M:N table.

    Composite PK is documented ("Composite PK (Many-to-Many)"); true
    composite primary keys are not available in this project's Django
    version (5.0). A UUID surrogate PK + UniqueConstraint(exercise,
    concept) is used instead (ENGINEERING DECISION — same uniqueness
    guarantee, consistent with the UUID PK strategy used across every
    other table in this schema).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
    )

    concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "exercise_concepts"

        indexes = [
            models.Index(
                fields=["concept"],
                name="idx_ec_concept",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "concept"],
                name="uq_exercise_concepts",
            ),
        ]

    def __str__(self):
        return f"{self.exercise_id}:{self.concept_id}"


class TestCase(models.Model):
    """
    CONFIRMED — Phase 8 §4.2 `test_cases` table, verbatim.

    input/expected_output type not documented; stored as TextField
    (ENGINEERING DECISION).
    """

    class Visibility(models.TextChoices):
        VISIBLE = "visible", "Visible"
        HIDDEN = "hidden", "Hidden"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )

    input = models.TextField()

    expected_output = models.TextField()

    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
    )

    class Meta:
        db_table = "test_cases"

        indexes = [
            models.Index(
                fields=["exercise"],
                name="idx_testcases_exercise",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    visibility__in=[
                        "visible",
                        "hidden",
                    ]
                ),
                name="ck_testcases_visibility",
            ),
        ]

    def __str__(self):
        return (
            f"TestCase({self.id}) "
            f"exercise={self.exercise_id} "
            f"vis={self.visibility}"
        )