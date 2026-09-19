from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.knowledge.models import ConceptFlawLog
from apps.knowledge.serializers import FlawLogEntrySerializer, MasteryOutputSerializer
from apps.knowledge.services import MasteryReadService


class MasteryReadView(APIView):
    """
    CONFIRMED concept — Phase 7 §4.6 MASTERY-READ.
    Response expanded to the full Phase 15 §19 output contract (Phase 7
    §4 header states its API table is abbreviated/non-exhaustive).
    `progress_value` (also named in Phase 7's abbreviated row) is
    omitted — it belongs to the Learning Progress bounded context
    (Phase 4 §6: "Student Progress *(يملكها Learning Progress context،
    ليس هنا)*"), which is not yet implemented; no fabricated value is
    returned in its place.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        results = MasteryReadService.get_all_concept_mastery_for_user(request.user)
        serialized = MasteryOutputSerializer(results, many=True).data
        return Response({"data": {"mastery": serialized}}, status=status.HTTP_200_OK)


class FlawLogReadView(APIView):
    """CONFIRMED — Phase 7 §4.6 FLAW-LOG-READ."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = ConceptFlawLog.objects.filter(user=request.user).order_by("concept__name")
        payload = [
            {"concept_id": entry.concept_id, "error_type": entry.error_type, "flagged": entry.flagged}
            for entry in entries
        ]
        serialized = FlawLogEntrySerializer(payload, many=True).data
        return Response({"data": {"flaw_log": serialized}}, status=status.HTTP_200_OK)