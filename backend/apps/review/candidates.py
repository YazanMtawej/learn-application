from apps.knowledge.services import ConceptFlawLogService, MasteryReadService
from apps.learning_content.models import Concept, Exercise

MANDATORY_TRIGGERS = {"module_completed", "assessment_remediation"}
ADAPTIVE_TRIGGERS = {"review_concept", "review_prerequisite"}


class ReviewCandidateService:
    """
    Phase 17 §7 Candidate Generation. Weak-concept detection reuses
    TASK 5's read services only (no duplicated Mastery/Flaw logic).
    """

    @staticmethod
    def concepts_for_module(module) -> list:
        return list(
            Concept.objects.filter(
                exercises__lesson__module=module
            ).distinct()
        )

    @staticmethod
    def is_weak(user, concept) -> bool:
        """Phase 17 §6/§7: active_flaw (F1) OR mastery_state == Developing."""
        if ConceptFlawLogService.has_active_flaw(user, concept):
            return True
        mastery = MasteryReadService.get_concept_mastery_output(user, concept)
        return mastery["mastery_state"] == "developing"

    @classmethod
    def select_target_concepts(cls, user, trigger_context: str, concepts: list) -> list:
        weak = [c for c in concepts if cls.is_weak(user, c)]
        if weak:
            return weak

        if trigger_context in MANDATORY_TRIGGERS:
            # Phase 17 §7 Fallback: confirmatory review covering the
            # module/scope even without a detected weakness — required
            # by Phase 1 §6 (mandatory post-Module review) and
            # FR-ASSESS-003 (mandatory remediation fallback).
            return concepts

        # E4 (Adaptive-triggered): no fallback — Phase 17 §7 DERIVED
        # rule, a non-mandatory trigger with nothing weak produces no
        # session at all.
        return []

    @staticmethod
    def select_item_exercise(concept):
        """
        Bank-first/deterministic selection (Phase 1 §12, Phase 17 §7).
        No question bank exists (see models.py docstring) — the
        deterministic substitute is the lowest-id published Exercise
        linked to the concept. Returns None if content is unavailable
        (Phase 17 §11: the item is skipped, not fabricated).
        """
        return (
            Exercise.objects.filter(
                concepts=concept, lifecycle_status=Exercise.LifecycleStatus.PUBLISHED
            )
            .order_by("id")
            .first()
        )