"""
AI Provider Abstraction Layer — Phase 6 §7.I / Phase 10 §6.

No specific vendor SDK (OpenAI/Anthropic/etc.) is integrated here:
Phase 12 §23 explicitly defers the final MVP base model/provider
identity (P12-D2 — "Requires live verification... not named or
committed to here"). `build_ai_provider()` defaults to
`NullAIProvider`, which always reports `available=False` — this is
the documented Fail-Soft behavior (Phase 10 AI-P6) for the period
before Phase 12/14 resolve an actual vendor, NOT a fabricated
integration. `HTTPAIProvider` is a generic, vendor-agnostic HTTP
adapter that can be pointed at any endpoint conforming to the
contract below once a provider is chosen — no code above this layer
(`services.py`, `policy.py`, API contracts) needs to change when that
happens (D3 / Phase 6 ADR-3: replacement = Configuration, not
Refactor).
"""

import abc
import dataclasses
import json
import time
import urllib.error
import urllib.request


@dataclasses.dataclass
class AIResponse:
    """Phase 10 §13 AI Response Contract (policy_check_result is added
    later, by the Policy layer — never supplied by the provider)."""

    available: bool
    malformed: bool = False
    response_type: str | None = None
    content: str | None = None
    hint_level: int | None = None
    related_concept_id: str | None = None
    confidence: float | None = None
    contains_code_snippet: bool = False
    safety_flags: list = dataclasses.field(default_factory=list)
    model_version: str = "unconfigured"
    latency_ms: int = 0


class AIProvider(abc.ABC):
    @abc.abstractmethod
    def generate_hint(self, payload: dict) -> AIResponse:
        ...


class NullAIProvider(AIProvider):
    """Default provider — no vendor configured yet (see module docstring)."""

    def generate_hint(self, payload: dict) -> AIResponse:
        return AIResponse(available=False, model_version="none")


class HTTPAIProvider(AIProvider):
    """
    Generic HTTP adapter. Expects the configured endpoint to accept a
    JSON POST of `payload` and return JSON with at least:
    {"content": str, "confidence": float, "contains_code_snippet": bool}.
    Any network/parse failure degrades to `available=False`
    (Phase 10 §15 Fail-Soft) rather than propagating an exception.
    """

    def __init__(self, url: str, timeout_seconds: int, model_version: str):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.model_version = model_version

    def generate_hint(self, payload: dict) -> AIResponse:
        started = time.monotonic()
        try:
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
            parsed = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return AIResponse(available=False, model_version=self.model_version)

        latency_ms = int((time.monotonic() - started) * 1000)

        content = parsed.get("content")
        if not isinstance(content, str) or not content.strip():
            return AIResponse(available=True, malformed=True, model_version=self.model_version, latency_ms=latency_ms)

        return AIResponse(
            available=True,
            malformed=False,
            response_type="hint",
            content=content,
            hint_level=payload.get("tutor_policy", {}).get("hint_level"),
            related_concept_id=parsed.get("related_concept_id"),
            confidence=parsed.get("confidence"),
            contains_code_snippet=bool(parsed.get("contains_code_snippet", False)),
            safety_flags=parsed.get("safety_flags") or [],
            model_version=self.model_version,
            latency_ms=latency_ms,
        )


def build_ai_provider() -> AIProvider:
    from django.conf import settings

    if settings.AI_PROVIDER_BACKEND == "http" and settings.AI_PROVIDER_HTTP_URL:
        return HTTPAIProvider(
            url=settings.AI_PROVIDER_HTTP_URL,
            timeout_seconds=settings.AI_PROVIDER_HTTP_TIMEOUT_SECONDS,
            model_version=settings.AI_PROVIDER_MODEL_VERSION,
        )
    return NullAIProvider()