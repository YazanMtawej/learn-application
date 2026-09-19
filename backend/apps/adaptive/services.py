from django.db import transaction

from apps.adaptive import actions
from apps.adaptive.candidates import Candidate, CandidateGenerator
from apps.adaptive.conflict_resolution import ConflictResolver
from apps.adaptive.context import ContextBuilder
from apps.adaptive.eligibility import EligibilityFilter
from apps.adaptive.models import AdaptiveDecision
from apps.adaptive.priority import PriorityLadder


class AdaptiveDecisionService:
    """
    Orchestrates the full Phase 16 §5 pipeline:
    Context → Candidate Generation → Eligibility Filtering →
    Priority Ladder → Conflict Resolution → Explainability → Persistence.

    Deterministic (Phase 16 §19): identical
    (StudentAdaptiveContext + ruleset_version + eligibility rules)
    always yields the same recommended_action. No randomness, no AI
    call anywhere in this path.
    """

    @classmethod
    @transaction.atomic
    def decide(cls, user, trigger_event: str, concept_id: str, remediation_pending: bool = False) -> AdaptiveDecision:
        from django.conf import settings

        context = ContextBuilder.build(user, [concept_id])
        concept_state = context.concept_states[concept_id]

        candidates = CandidateGenerator.generate(
            trigger_event, concept_id, concept_state, concept_state.active_flaw
        )

        eligible, rejected = EligibilityFilter.filter_candidates(
            candidates, context, remediation_pending=remediation_pending
        )

        if not eligible:
            # Phase 16 §18 Edge Case: no fabricated decision, no server
            # error surfaced to the student — documented STAY fallback.
            selected = Candidate(
                action_type=actions.STAY,
                target_concept_id=concept_id,
                rationale_tag="no_eligible_candidates",
            )
            reason = "no eligible progression action — awaiting new evidence or manual review"
        else:
            ranked = PriorityLadder.rank(eligible)
            selected = ConflictResolver.resolve(ranked, assessment_remediation_pending=remediation_pending)
            reason = cls._build_reason(selected, concept_state)

        key_signals = {
            "mastery_state": concept_state.mastery_state,
            "active_flaw": concept_state.active_flaw,
            "review_recommended": concept_state.review_recommended,
        }

        rejected_summary = [
            {"action_type": c.action_type, "reason": r} for c, r in rejected
        ] if rejected else None

        signals_snapshot = {
            "concept_states": {
                cid: {
                    "mastery_state": cs.mastery_state,
                    "mastery_score": cs.mastery_score,
                    "active_flaw": cs.active_flaw,
                    "review_recommended": cs.review_recommended,
                    "last_evidence_at": cs.last_evidence_at,
                }
                for cid, cs in context.concept_states.items()
            },
            "ai_concept_signal": context.ai_concept_signal,  # always None in MVP
            "reason": reason,
            "key_signals": key_signals,
            "rejected_candidates_summary": rejected_summary,
            "ruleset_version": settings.ADAPTIVE_RULESET_VERSION,
        }

        recommended_action = {
            "type": selected.action_type,
            "target_concept_id": selected.target_concept_id,
            "target_module_id": selected.target_module_id,
        }

        decision = AdaptiveDecision.objects.create(
            user=user,
            trigger_event=trigger_event,
            signals_snapshot=signals_snapshot,
            recommended_action=recommended_action,
        )
        return decision

    @staticmethod
    def _build_reason(selected: Candidate, concept_state) -> str:
        if selected.rationale_tag:
            return f"Selected {selected.action_type} due to: {selected.rationale_tag} (mastery_state={concept_state.mastery_state})."
        return f"Selected {selected.action_type} as default progression (mastery_state={concept_state.mastery_state})."


class AdaptiveReadService:
    """Phase 7 §4.3 PATH-CURRENT-equivalent read (Adaptive Learning owns 'recommended_next_action')."""

    @staticmethod
    def get_latest_decision(user) -> AdaptiveDecision | None:
        return AdaptiveDecision.objects.filter(user=user).order_by("-created_at").first()