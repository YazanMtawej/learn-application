from apps.adaptive import actions

"""
Priority Ladder — Phase 16 §10. Phase 16 itself labels this Ladder
"PROPOSED" (not APPROVED) and explicitly leaves the exact ordering
between rungs 5/6/7 open as P16-D1. This module implements the Ladder
exactly as Phase 16 §10 presents it — no ordering decision beyond what
Phase 16 itself already states is made here.
"""

RUNG_ACTIVE_FLAW = 2
RUNG_PREREQUISITE_WEAKNESS = 3
RUNG_MANDATORY_MODULE_REVIEW = 4
RUNG_RECENT_FAILURE = 5
RUNG_CONSISTENT_SUCCESS = 6
RUNG_MILESTONE = 7
RUNG_DEFAULT = 8


def rung_for(candidate) -> int:
    if candidate.rationale_tag == "mandatory_module_review":
        return RUNG_MANDATORY_MODULE_REVIEW
    if candidate.rationale_tag == "active_flaw":
        return RUNG_ACTIVE_FLAW
    if candidate.action_type == actions.REVIEW_PREREQUISITE:
        return RUNG_PREREQUISITE_WEAKNESS
    if candidate.rationale_tag == "recent_failure":
        return RUNG_RECENT_FAILURE
    if candidate.action_type in {actions.PRACTICE_HARDER, actions.CONTINUE} and candidate.rationale_tag == "":
        return RUNG_CONSISTENT_SUCCESS
    if candidate.action_type in {actions.UNLOCK_ASSESSMENT, actions.UNLOCK_PROJECT}:
        return RUNG_MILESTONE
    return RUNG_DEFAULT


class PriorityLadder:
    @staticmethod
    def rank(candidates: list) -> list:
        return sorted(candidates, key=rung_for)