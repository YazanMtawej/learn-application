from apps.learning_content.models import Exercise, Lesson


class EligibilityResult:
    def __init__(self, eligible: bool, reason: str | None = None):
        self.eligible = eligible
        self.reason = reason


class EligibilityFilter:
    """
    Phase 16 §7/§9. Applied in the documented order:
    Prerequisite Gate → Content Availability → Mastery Sufficiency →
    Entitlement → Assessment/Remediation State.

    Fail-open (Phase 4 §15 Invariant / Phase 16 §7): a `satisfied=None`
    prerequisite entry (technical read failure) does NOT block the
    candidate.
    """

    @staticmethod
    def check_prerequisite_gate(candidate, context) -> EligibilityResult:
        if candidate.target_concept_id is None:
            return EligibilityResult(eligible=True)

        entries = context.prerequisite_map.get(candidate.target_concept_id, [])
        for _, satisfied in entries:
            if satisfied is False:
                return EligibilityResult(
                    eligible=False, reason="prerequisite_not_satisfied"
                )
            # satisfied is None (fail-open) or True: does not block.
        return EligibilityResult(eligible=True)

    @staticmethod
    def check_content_availability(candidate) -> EligibilityResult:
        """
        DERIVED — Phase 4 §5 + Phase 8 §4.2 `lifecycle_status`. A
        candidate pointing at content that is not `published` is
        structurally unavailable to the student.
        """
        if candidate.action_type in {"CONTINUE", "PRACTICE_EASIER", "PRACTICE_HARDER"}:
            if candidate.target_concept_id is None:
                return EligibilityResult(eligible=True)
            has_published_exercise = Exercise.objects.filter(
                concepts__id=candidate.target_concept_id,
                lifecycle_status=Exercise.LifecycleStatus.PUBLISHED,
            ).exists()
            if not has_published_exercise:
                return EligibilityResult(eligible=False, reason="content_unavailable")
        return EligibilityResult(eligible=True)

    @staticmethod
    def check_mastery_sufficiency(candidate, context) -> EligibilityResult:
        """
        Phase 16 §7: PRACTICE_HARDER toward a concept that depends on
        this one as a Prerequisite requires mastery_state at or above
        the (deferred) gate threshold — same threshold source as
        check_prerequisite_gate.
        """
        if candidate.action_type != "PRACTICE_HARDER":
            return EligibilityResult(eligible=True)
        concept_state = context.concept_states.get(candidate.target_concept_id)
        if concept_state is None:
            return EligibilityResult(eligible=True)
        if concept_state.mastery_state in {"not_assessed", "insufficient_evidence"}:
            return EligibilityResult(eligible=False, reason="insufficient_mastery_for_escalation")
        return EligibilityResult(eligible=True)

    @staticmethod
    def check_remediation_state(candidate, remediation_pending: bool) -> EligibilityResult:
        """Phase 16 §7/§11: UNLOCK_ASSESSMENT blocked while a
        RemediationPath is active."""
        if candidate.action_type == "UNLOCK_ASSESSMENT" and remediation_pending:
            return EligibilityResult(eligible=False, reason="remediation_pending")
        return EligibilityResult(eligible=True)

    @classmethod
    def filter_candidates(cls, candidates, context, remediation_pending: bool = False):
        eligible, rejected = [], []
        for candidate in candidates:
            checks = [
                cls.check_prerequisite_gate(candidate, context),
                cls.check_content_availability(candidate),
                cls.check_mastery_sufficiency(candidate, context),
                cls.check_remediation_state(candidate, remediation_pending),
            ]
            failure = next((c for c in checks if not c.eligible), None)
            if failure is None:
                eligible.append(candidate)
            else:
                rejected.append((candidate, failure.reason))
        return eligible, rejected