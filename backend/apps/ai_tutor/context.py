import dataclasses
import json

from apps.knowledge.models import Evidence
from apps.knowledge.services import MasteryReadService
from apps.learning_content.models import Prerequisite


@dataclasses.dataclass
class TutorContext:
    """
    Phase 10 §9 Context Allow-list, built exclusively from Server-side,
    Owner-scoped queries. Hidden Test Cases are structurally excluded
    (never queried here) — Phase 9 §10 / Phase 10 ADR-10.2.
    """

    student_code: str
    evaluation_outcome: str
    evaluation_error_type: str | None
    lesson_objective: str
    lesson_excerpt: str
    visible_test_results: list
    concept_mastery_scores: dict  # concept_id -> float score only
    error_history: list  # [{correctness, error_type}], most recent first
    hint_history: list  # [level, ...] already-delivered levels for this attempt
    prerequisites: list  # [{concept_id, mastery_score}], optional/low-priority
    target_hint_level: int

    def to_dict(self, max_chars: int) -> dict:
        """
        Phase 10 §9 Context Priority: drop lowest-priority fields first
        when the serialized payload exceeds the configured budget.
        student_code/evaluation are never dropped.
        """
        payload = {
            "student_code": self.student_code,
            "evaluation": {"outcome": self.evaluation_outcome, "error_type": self.evaluation_error_type},
            "lesson_objective": self.lesson_objective,
            "hint_history": self.hint_history,
            "error_history": self.error_history,
            "concept_mastery_scores": self.concept_mastery_scores,
            "lesson_excerpt": self.lesson_excerpt,
            "visible_test_results": self.visible_test_results,
            "prerequisites": self.prerequisites,
        }

        drop_order = ["prerequisites", "lesson_excerpt", "concept_mastery_scores", "error_history", "hint_history"]
        for field_name in drop_order:
            if len(json.dumps(payload)) <= max_chars:
                break
            if field_name == "lesson_excerpt" and payload["lesson_excerpt"]:
                payload["lesson_excerpt"] = payload["lesson_excerpt"][: max_chars // 4]
            else:
                payload[field_name] = [] if isinstance(payload.get(field_name), list) else {}

        return payload


class TutorContextBuilder:
    @staticmethod
    def build(user, attempt, target_hint_level: int) -> TutorContext:
        from django.conf import settings

        exercise = attempt.exercise
        lesson = exercise.lesson
        evaluation_result = attempt.evaluation_result

        visible_results = []
        if hasattr(attempt, "execution") and attempt.execution.raw_output_ref:
            try:
                details = json.loads(attempt.execution.raw_output_ref)
            except (ValueError, TypeError):
                details = []
            for entry in details:
                if entry.get("visibility") == "visible":
                    visible_results.append(
                        {"passed": entry.get("passed", False), "stdout": entry.get("stdout", "")}
                    )

        concepts = list(exercise.concepts.all())
        concept_mastery_scores = {
            str(c.id): MasteryReadService.get_concept_mastery_output(user, c)["mastery_score"]
            for c in concepts
        }

        error_history = list(
            Evidence.objects.filter(user=user, concept__in=concepts)
            .exclude(pk=None)
            .order_by("-created_at")[: settings.AI_CONTEXT_ERROR_HISTORY_LIMIT]
            .values("correctness", "error_type")
        )

        hint_history = list(
            attempt.hints.filter(policy_check_result="approved").order_by("level").values_list("level", flat=True)
        )

        prerequisites = []
        for concept in concepts:
            for prereq in Prerequisite.objects.filter(target_concept=concept).select_related("source_concept"):
                score = MasteryReadService.get_concept_mastery_output(user, prereq.source_concept)["mastery_score"]
                prerequisites.append({"concept_id": str(prereq.source_concept_id), "mastery_score": score})

        return TutorContext(
            student_code=attempt.code,
            evaluation_outcome=evaluation_result.outcome,
            evaluation_error_type=evaluation_result.error_type,
            lesson_objective=lesson.objective,
            lesson_excerpt=lesson.content_ref[: settings.AI_CONTEXT_LESSON_EXCERPT_CHARS],
            visible_test_results=visible_results,
            concept_mastery_scores=concept_mastery_scores,
            error_history=error_history,
            hint_history=hint_history,
            prerequisites=prerequisites,
            target_hint_level=target_hint_level,
        )