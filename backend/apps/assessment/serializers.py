from rest_framework import serializers


class AssessmentStartRequestSerializer(serializers.Serializer):
    """CONFIRMED — Phase 7 §4.7 ASSESS-START path param: module_id."""

    module_id = serializers.UUIDField()


class AssessmentItemOutputSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    exercise_id = serializers.UUIDField()


class AssessmentStartResponseSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()
    questions = AssessmentItemOutputSerializer(many=True)


class AssessmentAnswerSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    code = serializers.CharField(allow_blank=False, trim_whitespace=False)


class AssessmentSubmitRequestSerializer(serializers.Serializer):
    """CONFIRMED — Phase 7 §4.7 ASSESS-SUBMIT Request: answers[]."""

    answers = AssessmentAnswerSerializer(many=True)


class AssessmentSubmitResponseSerializer(serializers.Serializer):
    """
    CONFIRMED fields — Phase 7 §4.7 ASSESS-SUBMIT Response:
    result, remediation_required?. `result` may read "in_progress"
    immediately after submit — Phase 6 §7.J mandates async Code
    Execution, so instantaneous finalization cannot be guaranteed;
    clients must poll the status endpoint (ENGINEERING DECISION
    extension, same as EXEC-STATUS) for the terminal result.
    """

    attempt_id = serializers.UUIDField()
    result = serializers.CharField()
    remediation_required = serializers.BooleanField()