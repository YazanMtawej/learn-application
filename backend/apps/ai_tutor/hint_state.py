from django.db.models import Max

from apps.ai_tutor.exceptions import InvalidTransitionError
from apps.ai_tutor.models import Hint

MAX_HINT_LEVEL = 3


class HintStateMachine:
    """
    Phase 2 SM-05 / Phase 16 §6: strictly sequential 1→2→3, no skipping.
    Current level = highest level with an APPROVED (i.e. delivered) Hint
    row for this attempt.
    """

    @staticmethod
    def get_current_level(attempt) -> int:
        result = Hint.objects.filter(attempt=attempt, policy_check_result=Hint.PolicyResult.APPROVED).aggregate(
            Max("level")
        )
        return result["level__max"] or 0

    @classmethod
    def validate_and_get_next_level(cls, attempt) -> int:
        current = cls.get_current_level(attempt)
        if current >= MAX_HINT_LEVEL:
            raise InvalidTransitionError(message="All available hint levels have already been delivered.")
        return current + 1