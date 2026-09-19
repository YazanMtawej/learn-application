from rest_framework import serializers

from apps.subscriptions.models import Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "code", "name"]
        read_only_fields = fields


class UpgradeRequestSerializer(serializers.Serializer):
    """CONFIRMED — Phase 7 §4.9 SUB-UPGRADE Request: plan_id, payment_method_ref."""

    plan_id = serializers.UUIDField()
    payment_method_ref = serializers.CharField(max_length=255)