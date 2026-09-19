import dataclasses

from apps.adaptive import actions


@dataclasses.dataclass
class Candidate:
    action_type: str
    target_concept_id: str | None = None
    target_module_id: str | None = None
    rationale_tag: str = ""


class CandidateGenerator:
    """
    Rule-Based candidate generation — Phase 16 §8. No AI involvement
    (Phase 16 AI-boundary invariant). Mapping from trigger pattern to
    candidate set follows Phase 16 §8's documented rule table literally.
    """

    @staticmethod
    def generate(trigger_event: str, concept_id: str, concept_state, active_flaw: bool) -> list:
        candidates = []

        if trigger_event == "module_completed":
            candidates.append(Candidate(actions.UNLOCK_ASSESSMENT, target_concept_id=concept_id))
            candidates.append(
                Candidate(actions.REVIEW_CONCEPT, target_concept_id=concept_id, rationale_tag="mandatory_module_review")
            )
            return candidates

        if concept_state.mastery_state == "insufficient_evidence":
            # Phase 16 §14/§17 Invariant: Insufficient Evidence is
            # "needs more data", never a trigger for REVIEW_* by itself.
            candidates.append(Candidate(actions.CONTINUE, target_concept_id=concept_id))
            candidates.append(Candidate(actions.PRACTICE_EASIER, target_concept_id=concept_id))
            return candidates

        if active_flaw:
            candidates.append(
                Candidate(actions.REVIEW_CONCEPT, target_concept_id=concept_id, rationale_tag="active_flaw")
            )
            candidates.append(Candidate(actions.PRACTICE_EASIER, target_concept_id=concept_id))

        if trigger_event == "submission_failed":
            candidates.append(
                Candidate(actions.TRIGGER_EXPLANATION, target_concept_id=concept_id, rationale_tag="recent_failure")
            )
            candidates.append(Candidate(actions.PRACTICE_EASIER, target_concept_id=concept_id))

        if trigger_event == "submission_passed" and concept_state.mastery_state in {"proficient", "mastered"}:
            candidates.append(Candidate(actions.PRACTICE_HARDER, target_concept_id=concept_id))
            candidates.append(Candidate(actions.UNLOCK_PROJECT, target_concept_id=concept_id))

        candidates.append(Candidate(actions.CONTINUE, target_concept_id=concept_id))
        return candidates