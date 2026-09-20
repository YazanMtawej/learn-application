from rest_framework import serializers


class HintResponseSerializer(serializers.Serializer):
    hint_level = serializers.IntegerField()
    content = serializers.CharField(allow_null=True)
    delivered = serializers.BooleanField()
    status = serializers.CharField(required=False, allow_null=True)


class HintStateSerializer(serializers.Serializer):
    current_level = serializers.IntegerField()
    max_reached = serializers.IntegerField()