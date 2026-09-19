from rest_framework import serializers


class RecommendedActionSerializer(serializers.Serializer):
    type = serializers.CharField()
    target_concept_id = serializers.CharField(allow_null=True)
    target_module_id = serializers.CharField(allow_null=True)


class AdaptiveDecisionSerializer(serializers.Serializer):
    """
    Phase 16 §21: only the 4 real columns (trigger_event,
    recommended_action, created_at, plus reason/key_signals surfaced
    from within signals_snapshot per Phase 16's own resolution) are
    exposed — signals_snapshot's full internal contents are NOT
    exposed verbatim to the client (Phase 16 §28: server-authoritative,
    not a data-dump surface).
    """

    trigger_event = serializers.CharField()
    recommended_action = RecommendedActionSerializer()
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()

    @classmethod
    def from_decision(cls, decision):
        return cls(
            {
                "trigger_event": decision.trigger_event,
                "recommended_action": decision.recommended_action,
                "reason": decision.signals_snapshot.get("reason", ""),
                "created_at": decision.created_at,
            }
        )