from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.execution.serializers import (
    SubmitRequestSerializer,
    SubmitResponseSerializer,
    serialize_status,
)
from apps.execution.services import ExecutionSubmissionService
from apps.execution.tasks import run_exercise_attempt


class ExecutionSubmitView(APIView):
    """CONFIRMED — Phase 7 §4.4 EXEC-SUBMIT."""

    permission_classes = [IsAuthenticated]

    def post(self, request, exercise_id):
        serializer = SubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = request.headers.get("Idempotency-Key")

        attempt, created = ExecutionSubmissionService.submit(
            user=request.user,
            exercise_id=exercise_id,
            code=serializer.validated_data["code"],
            idempotency_key=idempotency_key,
        )

        if created:
            transaction.on_commit(lambda: run_exercise_attempt.delay(str(attempt.id)))

        response_data = SubmitResponseSerializer(
            {"attempt_id": attempt.id, "status": "queued"}
        ).data
        return Response(
            {"data": response_data},
            status=status.HTTP_202_ACCEPTED,
        )


class ExecutionStatusView(APIView):
    """CONFIRMED — Phase 7 §4.4 EXEC-STATUS."""

    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = ExecutionSubmissionService.get_owned_attempt(request.user, attempt_id)
        return Response({"data": serialize_status(attempt)}, status=status.HTTP_200_OK)


class ExecutionCancelView(APIView):
    """CONFIRMED — Phase 7 §4.4 EXEC-CANCEL."""

    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        ExecutionSubmissionService.cancel(request.user, attempt_id)
        return Response({"data": {"status": "cancelled"}}, status=status.HTTP_200_OK)