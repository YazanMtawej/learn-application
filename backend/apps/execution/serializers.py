from rest_framework import serializers

from apps.execution.models import Execution, ExerciseAttempt


class SubmitRequestSerializer(serializers.Serializer):
    """
    CONFIRMED — Phase 7 §4.4 EXEC-SUBMIT Request: code, language_version.
    language_version is optional — Phase 7 §6: "معرّف نسخة اللغة (إن
    وُجد أكثر من نسخة لاحقًا)"; V1 supports exactly one Python version
    (D4), so it is accepted but not currently used for routing.
    """

    code = serializers.CharField(allow_blank=False, trim_whitespace=False)
    language_version = serializers.CharField(required=False, allow_blank=True)


class SubmitResponseSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()
    status = serializers.CharField()


class VisibleTestResultSerializer(serializers.Serializer):
    """
    Never includes hidden test cases (Phase 9 §10 — hidden tests must
    never reach the student). Filtered server-side in the view before
    serialization.
    """

    input = serializers.CharField()
    expected_output = serializers.CharField()
    actual_output = serializers.CharField()
    passed = serializers.BooleanField()


class EvaluationSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["pass", "fail"])
    error_type = serializers.CharField(allow_null=True)


API_STATUS_MAP = {
    None: "queued",
    Execution.ResultType.PASS: "completed",
    Execution.ResultType.FAIL: "completed",
    Execution.ResultType.RUNTIME_ERROR: "completed",
    Execution.ResultType.TIMEOUT: "timeout",
    Execution.ResultType.SYSTEM_ERROR: "system_error",
    Execution.ResultType.CANCELLED: "cancelled",
}


def serialize_status(attempt: ExerciseAttempt) -> dict:
    execution = getattr(attempt, "execution", None)
    result_type = execution.result_type if execution else None
    api_status = API_STATUS_MAP[result_type]

    payload = {"status": api_status}

    if api_status == "completed":
        evaluation_result = getattr(attempt, "evaluation_result", None)
        if evaluation_result is not None:
            payload["evaluation"] = {
                "result": evaluation_result.outcome,
                "error_type": evaluation_result.error_type,
            }

        visible_results = []
        if execution and execution.raw_output_ref:
            import json

            try:
                details = json.loads(execution.raw_output_ref)
            except (ValueError, TypeError):
                details = []

            test_cases_by_id = {
                str(tc.id): tc for tc in attempt.exercise.test_cases.filter(visibility="visible")
            }
            for entry in details:
                test_case = test_cases_by_id.get(entry.get("test_case_id"))
                if test_case is None:
                    continue
                visible_results.append(
                    {
                        "input": test_case.input,
                        "expected_output": test_case.expected_output,
                        "actual_output": entry.get("stdout", ""),
                        "passed": entry.get("passed", False),
                    }
                )
        payload["visible_results"] = visible_results

    return payload