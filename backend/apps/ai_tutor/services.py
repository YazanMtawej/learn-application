from django.db import transaction
from django.utils import timezone

from apps.ai_tutor.context import TutorContextBuilder
from apps.ai_tutor.exceptions import (
    AttemptNotEvaluatedError,
    HintNotApplicableError,
    HintQuotaExceededError,
)
from apps.ai_tutor.hint_state import HintStateMachine
from apps.ai_tutor.models import AIInteraction, Hint
from apps.ai_tutor.policy import PostCallPolicy
from apps.ai_tutor.prompt import EDUCATIONAL_POLICY_LAYER, SYSTEM_POLICY_LAYER, build_tutor_policy_layer
from apps.ai_tutor.provider import build_ai_provider
from apps.execution.services import ExecutionSubmissionService
from apps.subscriptions.services import SubscriptionService


class HintResult:
    def __init__(self, delivered: bool, hint_level: int, content: str | None, status: str | None = None):
        self.delivered = delivered
        self.hint_level = hint_level
        self.content = content
        self.status = status


class HintService:
    """
    Orchestrates the full Phase 10 §5/§8/§11 pipeline:
    Ownership → Deterministic-Gate/Eligibility (Pre-Call Policy) →
    Context Build → Provider Invocation (+ bounded Regenerate) →
    Post-Call Policy → Persistence.
    """

    @classmethod
    def get_owned_attempt(cls, user, attempt_id):
        return ExecutionSubmissionService.get_owned_attempt(user, attempt_id)

    @classmethod
    def request_hint(cls, user, attempt_id) -> HintResult:
        from django.conf import settings

        attempt = cls.get_owned_attempt(user, attempt_id)

        evaluation_result = getattr(attempt, "evaluation_result", None)
        if evaluation_result is None:
            # Deterministic-First Gate (Phase 10 §8): with no evaluation
            # yet, there is nothing ambiguous to hint about — reject
            # before ever considering the AI Provider Abstraction.
            raise AttemptNotEvaluatedError()

        if evaluation_result.outcome == "pass":
            raise HintNotApplicableError()

        cls._enforce_hint_quota(user)

        target_level = HintStateMachine.validate_and_get_next_level(attempt)

        context = TutorContextBuilder.build(user, attempt, target_level)
        provider = build_ai_provider()

        payload = {
            "system_policy": SYSTEM_POLICY_LAYER,
            "educational_policy": EDUCATIONAL_POLICY_LAYER,
            "tutor_policy": build_tutor_policy_layer(target_level),
            "context": context.to_dict(settings.AI_CONTEXT_MAX_CHARS),
            "student_request": "hint",
        }

        max_attempts = settings.AI_REGENERATE_MAX_ATTEMPTS + 1
        for _ in range(max_attempts):
            response = provider.generate_hint(payload)

            if not response.available:
                cls._log_interaction(user, response, AIInteraction.PolicyResult.UNAVAILABLE)
                return HintResult(delivered=False, hint_level=target_level, content=None, status="ai_unavailable")

            if response.malformed:
                cls._log_interaction(user, response, AIInteraction.PolicyResult.MALFORMED)
                continue

            policy_result = PostCallPolicy.evaluate(response, target_level)

            if policy_result.approved:
                cls._log_interaction(user, response, AIInteraction.PolicyResult.APPROVED)
                with transaction.atomic():
                    Hint.objects.create(
                        attempt=attempt,
                        level=target_level,
                        content=response.content,
                        policy_check_result=Hint.PolicyResult.APPROVED,
                        delivered_at=timezone.now(),
                    )
                return HintResult(delivered=True, hint_level=target_level, content=response.content)

            cls._log_interaction(user, response, AIInteraction.PolicyResult.REJECTED)
            Hint.objects.create(
                attempt=attempt,
                level=target_level,
                content=response.content,
                policy_check_result=Hint.PolicyResult.REJECTED,
                delivered_at=None,
            )
            # Regenerate — loop continues.

        return HintResult(delivered=False, hint_level=target_level, content=None, status="ai_unavailable")

    @staticmethod
    def _enforce_hint_quota(user):
        """
        Enforced only if a matching Entitlement row exists — same
        pattern as Task 4's execution quota (no numeric value invented;
        Phase 1 §16/Phase 10 P10-D15 leave this TBD).
        """
        from django.utils import timezone as tz

        entitlement = SubscriptionService.has_entitlement(user, "ai_hints_per_day")
        if entitlement is None or entitlement.limit_value is None:
            return

        today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = Hint.objects.filter(
            attempt__user=user, delivered_at__gte=today_start, policy_check_result=Hint.PolicyResult.APPROVED
        ).count()
        if today_count >= entitlement.limit_value:
            raise HintQuotaExceededError()

    @staticmethod
    def _log_interaction(user, response, policy_result):
        AIInteraction.objects.create(
            user=user,
            use_case="hint_generation",
            model_version=response.model_version,
            cost=0.0,  # ENGINEERING DECISION — provider cost reporting not wired (no vendor configured, see provider.py)
            latency_ms=response.latency_ms,
            policy_result=policy_result,
        )


class HintStateService:
    @staticmethod
    def get_state(user, attempt_id) -> dict:
        attempt = HintService.get_owned_attempt(user, attempt_id)
        current_level = HintStateMachine.get_current_level(attempt)
        return {"current_level": current_level, "max_reached": current_level}