from rest_framework import serializers

from apps.content_authoring.models import ContentDraft


class ContentDraftCreateSerializer(serializers.Serializer):
    """
    Request shape ENGINEERING DECISION — Phase 7 §4.10 documents this
    contract's Purpose/Actor/Auth only, without Request/Response
    columns (unlike other contracts in the same document). content_type
    + payload are the minimum fields needed to satisfy the confirmed
    `content_drafts` schema (Phase 8 §4.11).
    """

    content_type = serializers.ChoiceField(choices=ContentDraft.ContentType.choices)
    payload = serializers.JSONField()


class ContentDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentDraft
        fields = [
            "id",
            "content_type",
            "status",
            "validation_result",
            "published_lesson",
            "published_exercise",
        ]
        read_only_fields = fields