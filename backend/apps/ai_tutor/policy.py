import re

from apps.ai_tutor.prompt import LEAKAGE_MARKERS


class PolicyCheckResult:
    def __init__(self, approved: bool, reasons: list | None = None):
        self.approved = approved
        self.reasons = reasons or []


class PostCallPolicy:
    """
    Phase 10 §11 Post-Call Policy — deterministic, independent of the
    model (Phase 10 ADR-10.1: "الأمان لا يعتمد على حسن نية النموذج").

    All numeric thresholds below (code-line count) are PROPOSED
    heuristics — Phase 10 P10-D13 explicitly defers exact Solution
    Leakage thresholds to Phase 14 benchmarking. They are centralized
    in settings and are not presented as final calibrated values.
    """

    CODE_FENCE_PATTERN = re.compile(r"```[\s\S]*?```")

    @classmethod
    def evaluate(cls, ai_response, requested_level: int) -> PolicyCheckResult:
        reasons = []

        # Schema Validation
        if not ai_response.content or not ai_response.content.strip():
            reasons.append("empty_content")
            return PolicyCheckResult(approved=False, reasons=reasons)

        # System Prompt Leakage Check
        for marker in LEAKAGE_MARKERS:
            if marker in ai_response.content:
                reasons.append("system_prompt_leakage")

        # Code-in-Hint / Solution Leakage Check (Phase 1 §27 Acceptance
        # Criteria: "Hint 1 لا يحتوي أي كود قابل للنسخ المباشر كحل")
        from django.conf import settings

        code_lines = cls._count_code_lines(ai_response.content)
        if requested_level in (1, 2) and code_lines > settings.AI_HINT_CODE_LINE_THRESHOLD:
            reasons.append("code_in_hint")

        if reasons:
            return PolicyCheckResult(approved=False, reasons=reasons)
        return PolicyCheckResult(approved=True)

    @classmethod
    def _count_code_lines(cls, content: str) -> int:
        total = 0
        for block in cls.CODE_FENCE_PATTERN.findall(content):
            total += max(0, block.count("\n") - 1)
        return total