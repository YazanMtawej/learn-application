from apps.adaptive import actions
from apps.adaptive.priority import rung_for
from apps.adaptive.candidates import Candidate

class ConflictResolver:
    """
    Phase 16 §11 — the 5 documented conflict rules, applied in order.
    P16-D2 (undocumented tie-break cases) is explicitly NOT resolved
    here beyond what Phase 16 §11 itself states.
    """

    @staticmethod
    def resolve(ranked_candidates: list, assessment_remediation_pending: bool = False) -> "Candidate | None":
        if not ranked_candidates:
            return None

        # Rule: Assessment Result (Deterministic) has priority over any
        # Adaptive recommendation — Phase 16 §11.
        if assessment_remediation_pending:
            for candidate in ranked_candidates:
                if candidate.action_type == actions.REVIEW_CONCEPT and candidate.rationale_tag == "assessment_remediation":
                    return candidate

        top_rung = rung_for(ranked_candidates[0])
        tied = [c for c in ranked_candidates if rung_for(c) == top_rung]

        if len(tied) == 1:
            return tied[0]

        # Rule: REVIEW_PREREQUISITE beats REVIEW_CONCEPT on tie —
        # Phase 16 §11 (PROPOSED, tied to P16-D2, applied as documented).
        prereq_review = next((c for c in tied if c.action_type == actions.REVIEW_PREREQUISITE), None)
        if prereq_review is not None:
            return prereq_review

        # Rule: mandatory Module Review precedes both CONTINUE and
        # UNLOCK_ASSESSMENT; after a passed Review, UNLOCK_ASSESSMENT
        # precedes CONTINUE — Phase 16 §11.
        unlock_assessment = next((c for c in tied if c.action_type == actions.UNLOCK_ASSESSMENT), None)
        if unlock_assessment is not None:
            return unlock_assessment

        return tied[0]