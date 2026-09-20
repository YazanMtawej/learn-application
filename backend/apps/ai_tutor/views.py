from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_tutor.serializers import HintResponseSerializer, HintStateSerializer
from apps.ai_tutor.services import HintService, HintStateService


class HintRequestView(APIView):
    """
    CONFIRMED — Phase 7 §4.5 HINT-REQUEST. No request body is accepted
    beyond authentication (Phase 7: "— (السياق يُبنى من attempt)") — the
    server alone determines the next hint level; the client cannot
    request a specific level (Phase 16 §28 Security).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        result = HintService.request_hint(request.user, attempt_id)
        payload = {
            "hint_level": result.hint_level,
            "content": result.content,
            "delivered": result.delivered,
        }
        if result.status:
            payload["status"] = result.status
        serialized = HintResponseSerializer(payload).data
        return Response({"data": serialized}, status=status.HTTP_200_OK)


class HintStateView(APIView):
    """CONFIRMED — Phase 7 §4.5 HINT-STATE."""

    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        state = HintStateService.get_state(request.user, attempt_id)
        serialized = HintStateSerializer(state).data
        return Response({"data": serialized}, status=status.HTTP_200_OK)