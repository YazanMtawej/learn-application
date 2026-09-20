from django.db import transaction

from apps.execution.exceptions import AttemptNotOwnedError
from apps.execution.services import ExecutionSubmissionService
from apps.execution.tasks import run_exercise_attempt
from apps.learning_content.models import Concept, Module
from apps.review.candidates import ADAPTIVE_TRIGGERS, ReviewCandidateService
from apps.review.exceptions import (
    ReviewContentUnavailableError,
    ReviewItemNotOwnedError,
    ReviewSessionNotActiveError,
    ReviewSessionNotOwnedError,
)
from apps.review.models import ReviewItem, ReviewSession


class ReviewSessionService:
    """
    Phase 17 §9.1 Trigger-Based Review (MVP-only — no due_at/interval
    anywhere in this service, per Phase 17 §21).
    """

    @classmethod
    @transaction.atomic
    def create_session_for_trigger(
        cls, user, trigger_context: str, module_id=None, target_concept_id=None
    ) -> ReviewSession | None:
        if module_id is not None:
            module = Module.objects.get(id=module_id)
            concepts = ReviewCandidateService.concepts_for_module(module)
        elif target_concept_id is not None:
            concepts = [Concept.objects.get(id=target_concept_id)]
        else:
            concepts = []

        target_concepts = ReviewCandidateService.select_target_concepts(user, trigger_context, concepts)
        if not target_concepts:
            # Phase 17 §7 DERIVED: E4 with nothing weak → no session
            # (not an error condition for a background trigger).
            return None

        items_to_create = []
        for concept in target_concepts:
            exercise = ReviewCandidateService.select_item_exercise(concept)
            if exercise is None:
                continue  # Phase 17 §11: content unavailable → skip this item only
            items_to_create.append((concept, exercise))

        if not items_to_create:
            if trigger_context in {"module_completed", "assessment_remediation"}:
                raise ReviewContentUnavailableError()
            return None

        session = ReviewSession.objects.create(
            user=user, trigger_context=trigger_context, status=ReviewSession.Status.ACTIVE
        )
        ReviewItem.objects.bulk_create(
            [
                ReviewItem(review_session=session, concept=concept, question_ref=exercise)
                for concept, exercise in items_to_create
            ]
        )
        return session

    @staticmethod
    def get_owned_session(user, session_id) -> ReviewSession:
        try:
            return ReviewSession.objects.get(id=session_id, user=user)
        except (ReviewSession.DoesNotExist, ValueError, TypeError):
            raise ReviewSessionNotOwnedError()

    @staticmethod
    def get_owned_item(user, session_id, item_id) -> ReviewItem:
        try:
            return ReviewItem.objects.select_related("review_session").get(
                id=item_id, review_session_id=session_id, review_session__user=user
            )
        except (ReviewItem.DoesNotExist, ValueError, TypeError):
            raise ReviewItemNotOwnedError()

    @classmethod
    @transaction.atomic
    def submit_item_answer(cls, user, session_id, item_id, code: str, idempotency_key: str) -> ReviewItem:
        item = cls.get_owned_item(user, session_id, item_id)
        session = item.review_session

        if session.status != ReviewSession.Status.ACTIVE:
            raise ReviewSessionNotActiveError()

        if item.attempt_id is not None:
            # Idempotent: already answered — return existing state,
            # do not re-submit / re-execute / re-generate Evidence.
            return item

        attempt, created = ExecutionSubmissionService.submit(
            user=user,
            exercise_id=item.question_ref_id,
            code=code,
            idempotency_key=idempotency_key,
        )
        item.attempt = attempt
        item.save(update_fields=["attempt"])

        if created:
            transaction.on_commit(lambda: run_exercise_attempt.delay(str(attempt.id)))

        return item

    @classmethod
    @transaction.atomic
    def evaluate_session_completion(cls, session: ReviewSession) -> None:
        """
        Called by the signal handler once every item in the session has
        a non-null outcome. Sufficiency threshold: ENGINEERING DECISION
        — "all items pass" (Phase 17 §13/P17-D6 leaves the exact
        threshold undocumented; this is the minimal deterministic rule,
        not a final calibrated product decision).
        """
        items = list(session.items.all())
        if any(item.outcome is None for item in items):
            return

        all_passed = all(item.outcome == ReviewItem.Outcome.PASS for item in items)
        session.status = ReviewSession.Status.COMPLETED if all_passed else ReviewSession.Status.REMEDIATION
        session.save(update_fields=["status"])

    @classmethod
    def retry_failed_items(cls, user, session_id) -> ReviewSession | None:
        """
        Phase 17 §12: "فشل جزئي → Repeat Review بنطاق أضيق". Exact
        re-scoping mechanics are undocumented (same gap class as
        P17-D1/D5) — this minimal implementation re-scopes strictly to
        the concepts of failed items only, reusing the same candidate/
        session-creation path (no duplicated logic).
        """
        session = cls.get_owned_session(user, session_id)
        if session.status != ReviewSession.Status.REMEDIATION:
            raise ReviewSessionNotActiveError()

        failed_concept_ids = list(
            session.items.filter(outcome=ReviewItem.Outcome.FAIL).values_list("concept_id", flat=True)
        )
        if not failed_concept_ids:
            return None

        new_session = ReviewSession.objects.create(
            user=user, trigger_context=session.trigger_context, status=ReviewSession.Status.ACTIVE
        )
        items = []
        for concept_id in failed_concept_ids:
            from apps.learning_content.models import Concept as ConceptModel

            concept = ConceptModel.objects.get(id=concept_id)
            exercise = ReviewCandidateService.select_item_exercise(concept)
            if exercise is not None:
                items.append(ReviewItem(review_session=new_session, concept=concept, question_ref=exercise))
        if items:
            ReviewItem.objects.bulk_create(items)
        return new_session