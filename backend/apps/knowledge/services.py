from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.knowledge.mastery_states import (
    DEVELOPING,
    INSUFFICIENT_EVIDENCE,
    MASTERED,
    NOT_ASSESSED,
    PROFICIENT,
    STATE_ORDER,
)
from apps.knowledge.models import ConceptFlawLog, ConceptMastery, Evidence


class EvidenceQualityService:
    """
    PROPOSED — Phase 15 §7 (quality tiers confirmed as a concept;
    the exact classification rule is documented there as PROPOSED,
    pending P15-D3 weight calibration).
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    FAIL = "fail"

    HINT_ELIGIBLE_STRONG_TYPES = {"code_writing", "debugging"}

    @classmethod
    def classify(cls, evidence: Evidence) -> str:
        if not evidence.correctness:
            return cls.FAIL
        if evidence.hint_usage == 0 and evidence.exercise_type in cls.HINT_ELIGIBLE_STRONG_TYPES:
            return cls.STRONG
        if evidence.hint_usage <= 1 or evidence.exercise_type == "mcq":
            return cls.MEDIUM
        return cls.WEAK


class ConceptFlawLogService:
    """Phase 2 FLOW-KNOW-02 / Phase 15 §8 pattern detection."""

    @staticmethod
    @transaction.atomic
    def record_if_applicable(evidence: Evidence) -> None:
        if evidence.correctness or not evidence.error_type:
            return

        flaw_log, created = ConceptFlawLog.objects.select_for_update().get_or_create(
            user=evidence.user,
            concept=evidence.concept,
            error_type=evidence.error_type,
            defaults={"occurrence_count": 0},
        )
        flaw_log.register_occurrence(settings.CONCEPT_FLAW_OCCURRENCE_THRESHOLD)

    @staticmethod
    def has_active_flaw(user, concept) -> bool:
        return ConceptFlawLog.objects.filter(user=user, concept=concept, flagged=True).exists()


class MasteryCalculationService:
    """
    Rule-Based, Deterministic Mastery calculation — Phase 15 §11.
    No AI/LLM involvement anywhere in this service (Phase 15 §10/§28
    Invariant).

    All numeric thresholds below are ENGINEERING DECISIONS, centralized
    in settings, pending calibration per Phase 15 P15-D3 (quality
    weights), P15-D6 (sufficiency/promotion counts), P15-D7 (window
    size). They are provisional and reversible via
    `MASTERY_ALGORITHM_VERSION` — no number here is presented as a
    final product decision.
    """

    @classmethod
    @transaction.atomic
    def recalculate(cls, user, concept) -> ConceptMastery:
        previous = ConceptMastery.objects.filter(user=user, concept=concept).first()
        previous_state = previous.mastery_value.get("state", NOT_ASSESSED) if previous else NOT_ASSESSED
        previous_idx = STATE_ORDER.index(previous_state)

        window = list(
            Evidence.objects.filter(user=user, concept=concept)
            .select_related("attempt", "attempt__exercise")
            .order_by("-created_at")[: settings.MASTERY_WINDOW_SIZE]
        )
        count = len(window)
        active_flaw = ConceptFlawLogService.has_active_flaw(user, concept)

        if count == 0:
            final_state = NOT_ASSESSED
            score = 0.0
            summary = {"evidence_count": 0, "window_size": settings.MASTERY_WINDOW_SIZE}
            last_evidence_at = None
        else:
            passes = [e for e in window if e.correctness]
            correctness_ratio = len(passes) / count

            quality_counts = {"strong": 0, "medium": 0, "weak": 0, "fail": 0}
            for e in window:
                quality_counts[EvidenceQualityService.classify(e)] += 1
            strong_ratio = quality_counts["strong"] / count

            score = round(correctness_ratio * 0.7 + strong_ratio * 0.3, 4)

            if count < settings.MASTERY_MIN_EVIDENCE_FOR_SUFFICIENCY:
                candidate_state = INSUFFICIENT_EVIDENCE
            elif (
                correctness_ratio >= settings.MASTERY_MIN_CORRECTNESS_FOR_MASTERED
                and strong_ratio >= settings.MASTERY_MIN_STRONG_RATIO_FOR_MASTERED
            ):
                candidate_state = MASTERED
            elif correctness_ratio >= settings.MASTERY_MIN_CORRECTNESS_FOR_PROFICIENT:
                candidate_state = PROFICIENT
            else:
                candidate_state = DEVELOPING

            candidate_idx = STATE_ORDER.index(candidate_state)

            # Phase 15 §10: "لا قفزات مباشرة" — Not Assessed/Insufficient
            # Evidence cannot jump directly to Proficient/Mastered.
            if previous_idx <= STATE_ORDER.index(INSUFFICIENT_EVIDENCE) and candidate_idx >= STATE_ORDER.index(PROFICIENT):
                candidate_idx = STATE_ORDER.index(DEVELOPING)

            # Phase 15 §10: active Conceptual Flaw blocks Mastered specifically.
            if active_flaw and candidate_idx == STATE_ORDER.index(MASTERED):
                candidate_idx = STATE_ORDER.index(PROFICIENT)

            # Phase 15 §10: "الحد الأقصى للتراجع دفعة واحدة: خطوة واحدة".
            if candidate_idx < previous_idx:
                candidate_idx = max(candidate_idx, previous_idx - 1)

            final_state = STATE_ORDER[candidate_idx]
            summary = {
                "evidence_count": count,
                "window_size": settings.MASTERY_WINDOW_SIZE,
                "correctness_ratio": round(correctness_ratio, 4),
                "quality_distribution": quality_counts,
            }
            last_evidence_at = window[0].created_at.isoformat()

        final_idx = STATE_ORDER.index(final_state)
        review_recommended = active_flaw or (final_idx < previous_idx)

        reason = (
            f"State={final_state} (previous={previous_state}) derived from {count} recent "
            f"evidence record(s) within a window of {settings.MASTERY_WINDOW_SIZE}; "
            f"active_flaw={active_flaw}."
        )

        mastery_value = {
            "state": final_state,
            "score": score,
            "evidence_summary": summary,
            "review_recommended": review_recommended,
            "last_evidence_at": last_evidence_at,
            "reason": reason,
            "algorithm_version": settings.MASTERY_ALGORITHM_VERSION,
        }

        mastery, _ = ConceptMastery.objects.update_or_create(
            user=user, concept=concept, defaults={"mastery_value": mastery_value}
        )
        return mastery


class EvidenceIngestionService:
    """
    Consumes the `ExerciseEvaluated` event (Phase 4 §13) via the
    `EvaluationResult` post_save signal (see signals.py). Runs inside
    the same DB transaction TASK 4 already opened for evaluation
    finalization (Phase 8 §13 atomicity requirement) — no new
    transaction boundary is introduced here, and apps.execution is
    never imported at module load time by apps.execution itself (zero
    modification to TASK 4 files).
    """

    @staticmethod
    def ingest_from_evaluation(evaluation_result) -> None:
        attempt = evaluation_result.attempt
        exercise = attempt.exercise
        concept_ids = list(exercise.concepts.values_list("id", flat=True))

        # Equal Attribution — Phase 15 §5/P15-D1 (PROPOSED default in
        # the absence of a documented weighting column): one Evidence
        # row per linked concept, all attributed equally.
        for concept_id in concept_ids:
            evidence, created = Evidence.objects.get_or_create(
                attempt=attempt,
                concept_id=concept_id,
                defaults={
                    "user": attempt.user,
                    "correctness": evaluation_result.outcome == "pass",
                    "error_type": evaluation_result.error_type,
                    "hint_usage": 0,  # No Hint/AI Tutor system exists yet (out of TASK 5 scope).
                },
            )
            if not created:
                continue

            ConceptFlawLogService.record_if_applicable(evidence)
            MasteryCalculationService.recalculate(evidence.user, evidence.concept)


class MasteryReadService:
    """Phase 4 §14: Knowledge & Mastery is the sole read authority for its own state."""

    @staticmethod
    def get_concept_mastery_output(user, concept) -> dict:
        mastery = ConceptMastery.objects.filter(user=user, concept=concept).first()
        active_flaw = ConceptFlawLogService.has_active_flaw(user, concept)

        if mastery is None:
            return {
                "concept_id": str(concept.id),
                "mastery_state": NOT_ASSESSED,
                "mastery_score": 0.0,
                "evidence_summary": {"evidence_count": 0, "window_size": settings.MASTERY_WINDOW_SIZE},
                "active_flaw": active_flaw,
                "review_recommended": active_flaw,
                "last_evidence_at": None,
                "reason": "No evidence recorded yet for this concept.",
                "algorithm_version": settings.MASTERY_ALGORITHM_VERSION,
            }

        value = mastery.mastery_value
        return {
            "concept_id": str(concept.id),
            "mastery_state": value["state"],
            "mastery_score": value["score"],
            "evidence_summary": value["evidence_summary"],
            "active_flaw": active_flaw,
            "review_recommended": value["review_recommended"] or active_flaw,
            "last_evidence_at": value["last_evidence_at"],
            "reason": value["reason"],
            "algorithm_version": value["algorithm_version"],
        }

    @staticmethod
    def get_all_concept_mastery_for_user(user) -> list[dict]:
        from apps.learning_content.models import Concept

        return [
            MasteryReadService.get_concept_mastery_output(user, concept)
            for concept in Concept.objects.all().order_by("name")
        ]