from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content_authoring.serializers import (
    ContentDraftCreateSerializer,
    ContentDraftSerializer,
)
from apps.content_authoring.services import ContentAuthoringService
from apps.identity.permissions import IsAdmin


class ContentDraftCreateView(APIView):
    """
    CONFIRMED — Phase 7 §4.10 CONTENT-DRAFT-CREATE.

    Auth mapping (documented deviation, not silent): Phase 7 §4.10
    specifies `Role=ContentAuthor`, but no such role exists in the
    project's confirmed 4-role RBAC enum (Phase 1 §2: student,
    instructor, organization, admin). This is an OPEN DOCUMENTATION GAP
    (see TASK 3 final report). Resolved here via the minimal reversible
    mapping of Content Authoring access to the existing `Admin` role
    (Phase 1 §2: Admin has full RBAC-controlled system access; Phase 3
    RV-4 confirms Content Authoring is internal-team-only usage in
    MVP), rather than inventing a new role/migration.
    """

    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = ContentDraftCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        draft = ContentAuthoringService.create_draft(
            author=request.user,
            content_type=serializer.validated_data["content_type"],
            payload=serializer.validated_data["payload"],
        )

        return Response(
            {"data": ContentDraftSerializer(draft).data}, status=status.HTTP_201_CREATED
        )


class ContentDraftPublishView(APIView):
    """CONFIRMED — Phase 7 §4.10 CONTENT-PUBLISH. Same role-mapping
    rationale as ContentDraftCreateView."""

    permission_classes = [IsAdmin]

    def post(self, request, draft_id):
        draft = ContentAuthoringService.publish(draft_id)
        return Response({"data": ContentDraftSerializer(draft).data}, status=status.HTTP_200_OK)