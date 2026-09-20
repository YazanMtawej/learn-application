from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assessment.serializers import (
    AssessmentStartRequestSerializer,
    AssessmentStartResponseSerializer,
    AssessmentSubmitRequestSerializer,
    AssessmentSubmitResponseSerializer,
)
from apps.assessment.services import (
    AssessmentAttemptService,
    AssessmentReadService,
)


class AssessmentStartView(APIView):
    """CONFIRMED — Phase 7 §4.7 ASSESS-START."""

    permission_classes = [IsAuthenticated]

    def post(self, request, module_id):
        attempt = AssessmentAttemptService.start_attempt(request.user, module_id)
        items = attempt.assessment.items.all()

        payload = {
            "attempt_id": attempt.id,
            "questions": [{"item_id": i.id, "exercise_id": i.exercise_id} for i in items],
        }
        serialized = AssessmentStartResponseSerializer(payload).data
        return Response({"data": serialized}, status=status.HTTP_201_CREATED)


class AssessmentSubmitView(APIView):
    """CONFIRMED — Phase 7 §4.7 ASSESS-SUBMIT."""

    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        serializer = AssessmentSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_prefix = request.headers.get("Idempotency-Key") or f"assess-{attempt_id}"

        attempt = AssessmentAttemptService.submit_answers(
            user=request.user,
            attempt_id=attempt_id,
            answers=serializer.validated_data["answers"],
            idempotency_prefix=idempotency_prefix,
        )

        status_payload = AssessmentReadService.get_attempt_status(attempt)
        serialized = AssessmentSubmitResponseSerializer(status_payload).data
        return Response({"data": serialized}, status=status.HTTP_202_ACCEPTED)


class AssessmentAttemptStatusView(APIView):
    """
    ENGINEERING DECISION — not a Phase 7 Contract ID. Required by the
    mandatory async execution architecture (Phase 6 §7.J): the client
    must be able to poll for the terminal result after ASSESS-SUBMIT
    returns `result: in_progress`.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = AssessmentAttemptService.get_owned_attempt(request.user, attempt_id)
        payload = AssessmentReadService.get_attempt_status(attempt)
        serialized = AssessmentSubmitResponseSerializer(payload).data
        return Response({"data": serialized}, status=status.HTTP_200_OK)