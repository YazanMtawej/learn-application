from rest_framework import serializers


class MasteryOutputSerializer(serializers.Serializer):
    """Phase 15 §19 Conceptual Mastery Output Contract."""

    concept_id = serializers.UUIDField()
    mastery_state = serializers.CharField()
    mastery_score = serializers.FloatField()
    evidence_summary = serializers.DictField()
    active_flaw = serializers.BooleanField()
    review_recommended = serializers.BooleanField()
    last_evidence_at = serializers.CharField(allow_null=True)
    reason = serializers.CharField()
    algorithm_version = serializers.CharField()


class FlawLogEntrySerializer(serializers.Serializer):
    concept_id = serializers.UUIDField()
    error_type = serializers.CharField()
    flagged = serializers.BooleanField()