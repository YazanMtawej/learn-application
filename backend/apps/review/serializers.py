from rest_framework import serializers


class ReviewStartRequestSerializer(serializers.Serializer):
    """CONFIRMED — Phase 7 §4.7 REVIEW-START Request: trigger_context (module_id)."""

    module_id = serializers.UUIDField()


class ReviewItemOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    concept_id = serializers.UUIDField()
    outcome = serializers.CharField(allow_null=True)


class ReviewStartResponseSerializer(serializers.Serializer):
    review_session_id = serializers.UUIDField()
    items = ReviewItemOutputSerializer(many=True)


class ReviewSubmitItemRequestSerializer(serializers.Serializer):
    """CONFIRMED — Phase 7 §4.7 REVIEW-SUBMIT-ITEM Request: answer."""

    answer = serializers.CharField(allow_blank=False, trim_whitespace=False)


class ReviewSubmitItemResponseSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    outcome = serializers.CharField(allow_null=True)
    status = serializers.CharField()