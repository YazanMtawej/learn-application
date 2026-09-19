import dataclasses

from apps.knowledge.services import MasteryReadService
from apps.learning_content.models import Concept, Exercise, Lesson, Module, Prerequisite


@dataclasses.dataclass
class ConceptState:
    concept_id: str
    mastery_state: str
    mastery_score: float
    active_flaw: bool
    review_recommended: bool
    last_evidence_at: str | None


@dataclasses.dataclass
class StudentAdaptiveContext:
    """
    CONFIRMED shape — Phase 16 §5 StudentAdaptiveContext (Read Model,
    built at request time, not a stored table — Phase 16 §5: "يُبنى وقت
    الطلب، وليس جدولًا مخزَّنًا جديدًا").
    """

    user_id: str
    concept_states: dict  # concept_id -> ConceptState
    prerequisite_map: dict  # concept_id -> list[(prereq_concept_id, satisfied: bool | None)]
    ai_concept_signal: dict | None  # always None in MVP — Phase 16 §16


class ContextBuilder:
    """
    Builds StudentAdaptiveContext exclusively from Server-side,
    Owner-scoped queries (Phase 16 §28 Security). No input is ever
    accepted from the client.
    """

    @staticmethod
    def build(user, concept_ids: list) -> StudentAdaptiveContext:
        concept_states = {}
        for concept_id in concept_ids:
            concept = Concept.objects.get(id=concept_id)
            mastery_output = MasteryReadService.get_concept_mastery_output(user, concept)
            concept_states[str(concept_id)] = ConceptState(
                concept_id=str(concept_id),
                mastery_state=mastery_output["mastery_state"],
                mastery_score=mastery_output["mastery_score"],
                active_flaw=mastery_output["active_flaw"],
                review_recommended=mastery_output["review_recommended"],
                last_evidence_at=mastery_output["last_evidence_at"],
            )

        prerequisite_map = ContextBuilder._build_prerequisite_map(user, concept_ids)

        return StudentAdaptiveContext(
            user_id=str(user.id),
            concept_states=concept_states,
            prerequisite_map=prerequisite_map,
            ai_concept_signal=None,  # Phase 16 §16: disabled in MVP decision path.
        )

    @staticmethod
    def _build_prerequisite_map(user, concept_ids: list) -> dict:
        """
        Fail-open per Phase 16 §7/§15/Phase 4 §15 Invariant: a technical
        read error yields `satisfied=None` (last-known-safe fallback,
        treated as non-blocking by the eligibility layer), never a
        forced "unsatisfied" verdict.
        """
        result = {}
        for concept_id in concept_ids:
            prereqs = Prerequisite.objects.filter(target_concept_id=concept_id).select_related(
                "source_concept"
            )
            entries = []
            for prereq in prereqs:
                try:
                    mastery_output = MasteryReadService.get_concept_mastery_output(
                        user, prereq.source_concept
                    )
                    satisfied = ContextBuilder._meets_prerequisite_threshold(
                        mastery_output["mastery_state"]
                    )
                except Exception:
                    # Fail-open: technical read failure, not "unsatisfied".
                    satisfied = None
                entries.append((str(prereq.source_concept_id), satisfied))
            result[str(concept_id)] = entries
        return result

    @staticmethod
    def _meets_prerequisite_threshold(mastery_state: str) -> bool:
        """
        DEFERRED threshold — Phase 15 P15-D5 / Phase 16 P16-D4: "هل
        عتبة Prerequisite Gate = Proficient أم Mastered؟" is explicitly
        unresolved in both Phase 15 and Phase 16. `PREREQUISITE_GATE_MIN_STATE`
        is a settings value (not a hardcoded literal) so this remains
        reversible and is never presented as a final product decision.
        """
        from django.conf import settings

        from apps.knowledge.mastery_states import STATE_ORDER

        required_idx = STATE_ORDER.index(settings.PREREQUISITE_GATE_MIN_STATE)
        actual_idx = STATE_ORDER.index(mastery_state)
        return actual_idx >= required_idx