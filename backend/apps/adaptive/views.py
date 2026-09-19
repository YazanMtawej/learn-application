from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.adaptive.serializers import AdaptiveDecisionSerializer
from apps.adaptive.services import AdaptiveReadService


class AdaptiveCurrentView(APIView):
    """
    Read-only. No write endpoint of any kind is exposed — Phase 16
    §28/§30: the client can never trigger, force, or overwrite a
    Decision. Decisions are produced only as an internal side effect
    of documented trigger events (module completion, submission
    evaluation) via AdaptiveDecisionService.decide, called from
    server-side event handlers, never from a public POST endpoint.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        decision = AdaptiveReadService.get_latest_decision(request.user)
        if decision is None:
            return Response(
                {"data": {"recommended_action": None, "reason": "No adaptive decision recorded yet."}},
                status=status.HTTP_200_OK,
            )
        serialized = AdaptiveDecisionSerializer.from_decision(decision).data
        return Response({"data": serialized}, status=status.HTTP_200_OK)