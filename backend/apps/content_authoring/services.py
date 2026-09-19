from django.db import transaction

from apps.content_authoring.exceptions import (
    ContentDraftNotFoundError,
    DraftAlreadyPublishedError,
    ValidationFailedError,
)
from apps.content_authoring.models import ContentDraft
from apps.learning_content.models import (
    Concept,
    Exercise,
    ExerciseConcept,
    Lesson,
    Module,
    TestCase,
)


class ContentValidationService:
    """
    Deterministic validation, matching Phase 1 §11 ("لا نشر بدون
    Validation حتمية") and Phase 4 §4 TestCase Invariant ("يجب توفر
    Hidden + Visible معًا لتمارين Code Writing").

    The internal shape of `ContentDraft.payload` is not specified
    anywhere in Phase 0-17 (Phase 8 §4.11 documents only that it is a
    jsonb column). The required-key structure checked below is an
    ENGINEERING DECISION — the minimum needed to construct the already
    -confirmed Lesson/Exercise/TestCase domain rows, not an invented
    business rule about what content *means*.
    """

    @staticmethod
    def validate_lesson_payload(payload: dict) -> list[str]:
        errors = []
        module_id = payload.get("module_id")
        objective = payload.get("objective")
        content_ref = payload.get("content_ref")
        order_index = payload.get("order_index")
        concept_id = payload.get("concept_id")

        if not module_id:
            errors.append("module_id is required.")
        elif not Module.objects.filter(id=module_id).exists():
            errors.append("module_id does not reference an existing module.")

        if not objective:
            errors.append("objective is required.")
        if not content_ref:
            errors.append("content_ref is required.")
        if order_index is None or not isinstance(order_index, int):
            errors.append("order_index is required and must be an integer.")

        if concept_id and not Concept.objects.filter(id=concept_id).exists():
            errors.append("concept_id does not reference an existing concept.")

        return errors

    @staticmethod
    def validate_exercise_payload(payload: dict) -> list[str]:
        errors = []
        lesson_id = payload.get("lesson_id")
        exercise_type = payload.get("type")
        difficulty = payload.get("difficulty")
        concept_ids = payload.get("concept_ids") or []
        test_cases = payload.get("test_cases") or []

        if not lesson_id:
            errors.append("lesson_id is required.")
        elif not Lesson.objects.filter(id=lesson_id).exists():
            errors.append("lesson_id does not reference an existing lesson.")

        if exercise_type not in {c[0] for c in Exercise.ExerciseType.choices}:
            errors.append("type must be one of code_writing, debugging, mcq.")

        if difficulty is None or not isinstance(difficulty, int):
            errors.append("difficulty is required and must be an integer.")

        if not concept_ids:
            errors.append("concept_ids must contain at least one concept.")
        else:
            existing_count = Concept.objects.filter(id__in=concept_ids).count()
            if existing_count != len(set(concept_ids)):
                errors.append("concept_ids contains one or more non-existent concepts.")

        if not test_cases:
            errors.append("test_cases must contain at least one entry.")
        else:
            visibilities = []
            for index, tc in enumerate(test_cases):
                tc_input = tc.get("input")
                tc_expected = tc.get("expected_output")
                tc_visibility = tc.get("visibility")
                if tc_input is None or tc_expected is None:
                    errors.append(f"test_cases[{index}] requires input and expected_output.")
                if tc_visibility not in {c[0] for c in TestCase.Visibility.choices}:
                    errors.append(f"test_cases[{index}] visibility must be 'visible' or 'hidden'.")
                else:
                    visibilities.append(tc_visibility)

            if TestCase.Visibility.VISIBLE not in visibilities:
                errors.append("At least one visible test case is required.")

            # Phase 4 §4 TestCase Invariant: code_writing exercises require
            # both visible and hidden test cases together.
            if exercise_type == Exercise.ExerciseType.CODE_WRITING:
                if TestCase.Visibility.HIDDEN not in visibilities:
                    errors.append(
                        "code_writing exercises require at least one hidden test case "
                        "in addition to a visible one."
                    )

        return errors

    @classmethod
    def validate(cls, draft: ContentDraft) -> list[str]:
        if draft.content_type == ContentDraft.ContentType.LESSON:
            return cls.validate_lesson_payload(draft.payload)
        return cls.validate_exercise_payload(draft.payload)


class ContentAuthoringService:
    """Application-layer content authoring logic (Phase 6 §5, Phase 4 §12)."""

    @staticmethod
    @transaction.atomic
    def create_draft(author, content_type: str, payload: dict) -> ContentDraft:
        return ContentDraft.objects.create(
            author=author,
            content_type=content_type,
            payload=payload,
            status=ContentDraft.Status.DRAFT,
        )

    @staticmethod
    def get_draft(draft_id):
        try:
            return ContentDraft.objects.get(id=draft_id)
        except (ContentDraft.DoesNotExist, ValueError, TypeError):
            raise ContentDraftNotFoundError()

    @classmethod
    @transaction.atomic
    def publish(cls, draft_id) -> ContentDraft:
        draft = cls.get_draft(draft_id)

        if draft.status == ContentDraft.Status.PUBLISHED:
            raise DraftAlreadyPublishedError()

        errors = ContentValidationService.validate(draft)
        if errors:
            draft.status = ContentDraft.Status.DRAFT
            draft.validation_result = "; ".join(errors)
            draft.save(update_fields=["status", "validation_result", "updated_at"])
            raise ValidationFailedError(message="; ".join(errors))

        draft.validation_result = "Validation passed."
        draft.status = ContentDraft.Status.VALIDATED

        if draft.content_type == ContentDraft.ContentType.LESSON:
            entity = cls._materialize_lesson(draft.payload)
            draft.published_lesson = entity
        else:
            entity = cls._materialize_exercise(draft.payload)
            draft.published_exercise = entity

        draft.status = ContentDraft.Status.PUBLISHED
        draft.save(
            update_fields=[
                "status", "validation_result", "published_lesson", "published_exercise", "updated_at",
            ]
        )
        return draft

    @staticmethod
    def _materialize_lesson(payload: dict) -> Lesson:
        return Lesson.objects.create(
            module_id=payload["module_id"],
            concept_id=payload.get("concept_id"),
            objective=payload["objective"],
            content_ref=payload["content_ref"],
            order_index=payload["order_index"],
        )

    @staticmethod
    def _materialize_exercise(payload: dict) -> Exercise:
        exercise = Exercise.objects.create(
            lesson_id=payload["lesson_id"],
            type=payload["type"],
            difficulty=payload["difficulty"],
            lifecycle_status=Exercise.LifecycleStatus.PUBLISHED,
        )

        ExerciseConcept.objects.bulk_create(
            [
                ExerciseConcept(exercise=exercise, concept_id=concept_id)
                for concept_id in payload["concept_ids"]
            ]
        )

        TestCase.objects.bulk_create(
            [
                TestCase(
                    exercise=exercise,
                    input=tc["input"],
                    expected_output=tc["expected_output"],
                    visibility=tc["visibility"],
                )
                for tc in payload["test_cases"]
            ]
        )

        return exercise