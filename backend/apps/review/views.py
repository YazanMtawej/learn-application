from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.review.serializers import (
    ReviewStartRequestSerializer,
    ReviewStartResponseSerializer,
    ReviewSubmitItemRequestSerializer,
    ReviewSubmitItemResponseSerializer,
)
from apps.review.services import ReviewSessionService


class ReviewStartView(APIView):
    """
    CONFIRMED — Phase 7 §4.7 REVIEW-START. Client declares which module
    triggered this (E1) — server independently computes weak concepts,
    item selection, and eligibility; the client cannot influence which
    concepts/items are chosen (Phase 17 §7/§26 Server Authority).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReviewStartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ReviewSessionService.create_session_for_trigger(
            user=request.user,
            trigger_context="module_completed",
            module_id=serializer.validated_data["module_id"],
        )

        payload = {
            "review_session_id": session.id,
            "items": [{"id": i.id, "concept_id": i.concept_id, "outcome": i.outcome} for i in session.items.all()],
        }
        serialized = ReviewStartResponseSerializer(payload).data
        return Response({"data": serialized}, status=status.HTTP_201_CREATED)


class ReviewSubmitItemView(APIView):
    """CONFIRMED — Phase 7 §4.7 REVIEW-SUBMIT-ITEM."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id, item_id):
        serializer = ReviewSubmitItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = request.headers.get("Idempotency-Key") or f"review-{item_id}"

        item = ReviewSessionService.submit_item_answer(
            user=request.user,
            session_id=session_id,
            item_id=item_id,
            code=serializer.validated_data["answer"],
            idempotency_key=idempotency_key,
        )

        payload = {
            "item_id": item.id,
            "outcome": item.outcome,
            "status": "completed" if item.outcome else "queued",
        }
        serialized = ReviewSubmitItemResponseSerializer(payload).data
        return Response({"data": serialized}, status=status.HTTP_202_ACCEPTED)