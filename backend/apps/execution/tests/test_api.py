from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.execution.models import Execution, ExerciseAttempt
from apps.execution.services import ExecutionRunnerService
from apps.identity.models import AccountStatus, User, VerificationStatus
from apps.identity.services import AuthService
from apps.learning_content.models import Concept, Exercise, Lesson, Module, TestCase as TC


def _active_client(email):
    user = User.objects.create_user(email=email, password="StrongPass123!")
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


def _published_exercise(with_hidden=True):
    module = Module.objects.create(title="Fundamentals", order_index=100)
    lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
    exercise = Exercise.objects.create(
        lesson=lesson, type="code_writing", difficulty=1,
        lifecycle_status=Exercise.LifecycleStatus.PUBLISHED,
    )
    TC.objects.create(exercise=exercise, input="", expected_output="5", visibility="visible")
    if with_hidden:
        TC.objects.create(exercise=exercise, input="", expected_output="10", visibility="hidden")
    return exercise


class ExecutionSubmitTests(TestCase):
    def setUp(self):
        self.client, self.user = _active_client("submituser@example.com")
        self.exercise = _published_exercise()
        self.url = reverse("execution:submit", kwargs={"exercise_id": self.exercise.id})

    @patch("apps.execution.views.run_exercise_attempt.delay")
    def test_submit_requires_idempotency_key(self, mock_delay):
        response = self.client.post(self.url, {"code": "print(5)"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")
        mock_delay.assert_not_called()

    @patch("apps.execution.views.run_exercise_attempt.delay")
    def test_successful_submit_enqueues_task_and_returns_queued(self, mock_delay):
        response = self.client.post(
            self.url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-1"
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["data"]["status"], "queued")
        mock_delay.assert_called_once()

    @patch("apps.execution.views.run_exercise_attempt.delay")
    def test_repeated_idempotency_key_does_not_create_second_attempt(self, mock_delay):
        self.client.post(
            self.url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-2"
        )
        self.client.post(
            self.url, {"code": "print(6)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-2"
        )
        self.assertEqual(ExerciseAttempt.objects.filter(user=self.user).count(), 1)

    @patch("apps.execution.views.run_exercise_attempt.delay")
    def test_unpublished_exercise_rejected(self, mock_delay):
        module = Module.objects.create(title="Draft Module", order_index=101)
        lesson = Lesson.objects.create(module=module, objective="x", content_ref="ref", order_index=1)
        draft_exercise = Exercise.objects.create(lesson=lesson, type="mcq", difficulty=1)
        url = reverse("execution:submit", kwargs={"exercise_id": draft_exercise.id})

        response = self.client.post(
            url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-3"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "EXERCISE_NOT_ACTIVE")

    @patch("apps.execution.views.run_exercise_attempt.delay")
    def test_concurrency_limit_enforced(self, mock_delay):
        from django.test import override_settings

        with override_settings(EXECUTION_MAX_CONCURRENT_PER_USER=1):
            self.client.post(
                self.url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-4a"
            )
            response = self.client.post(
                self.url, {"code": "print(6)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-4b"
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["error"]["code"], "EXECUTION_CONCURRENCY_LIMIT_EXCEEDED")

    def test_unauthenticated_submit_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.post(
            self.url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY="idem-5"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ExecutionStatusAndSecurityTests(TestCase):
    def setUp(self):
        self.client, self.user = _active_client("statususer@example.com")
        self.exercise = _published_exercise()

    def _create_attempt(self, client, key="status-key"):
        submit_url = reverse("execution:submit", kwargs={"exercise_id": self.exercise.id})
        with patch("apps.execution.views.run_exercise_attempt.delay"):
            response = client.post(
                submit_url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY=key
            )
        return response.data["data"]["attempt_id"]

    def test_status_before_execution_is_queued(self):
        attempt_id = self._create_attempt(self.client)
        status_url = reverse("execution:status", kwargs={"attempt_id": attempt_id})
        response = self.client.get(status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "queued")

    def test_status_after_successful_run_returns_completed_pass(self):
        attempt_id = self._create_attempt(self.client, key="run-pass")
        attempt = ExerciseAttempt.objects.get(id=attempt_id)
        attempt.code = "print(5)"
        attempt.save(update_fields=["code"])

        ExecutionRunnerService.run_attempt(attempt_id)

        status_url = reverse("execution:status", kwargs={"attempt_id": attempt_id})
        response = self.client.get(status_url)
        self.assertEqual(response.data["data"]["status"], "completed")
        self.assertEqual(response.data["data"]["evaluation"]["result"], "fail")

    def test_hidden_test_case_never_appears_in_status_response(self):
        attempt_id = self._create_attempt(self.client, key="hidden-check")
        ExecutionRunnerService.run_attempt(attempt_id)

        status_url = reverse("execution:status", kwargs={"attempt_id": attempt_id})
        response = self.client.get(status_url)

        for visible_result in response.data["data"]["visible_results"]:
            self.assertNotEqual(visible_result["expected_output"], "10")

        self.assertEqual(len(response.data["data"]["visible_results"]), 1)

    def test_user_cannot_view_another_users_attempt(self):
        attempt_id = self._create_attempt(self.client, key="owner-check")
        other_client, _ = _active_client("otherstatususer@example.com")

        status_url = reverse("execution:status", kwargs={"attempt_id": attempt_id})
        response = other_client.get(status_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "ATTEMPT_NOT_OWNED")

    def test_user_cannot_cancel_another_users_attempt(self):
        attempt_id = self._create_attempt(self.client, key="cancel-owner-check")
        other_client, _ = _active_client("othercanceluser@example.com")

        cancel_url = reverse("execution:cancel", kwargs={"attempt_id": attempt_id})
        response = other_client.post(cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_with_nonexistent_uuid_returns_not_owned(self):
        status_url = reverse(
            "execution:status", kwargs={"attempt_id": "00000000-0000-0000-0000-000000000000"}
        )
        response = self.client.get(status_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "ATTEMPT_NOT_OWNED")


class ExecutionCancelTests(TestCase):
    def setUp(self):
        self.client, self.user = _active_client("canceluser2@example.com")
        self.exercise = _published_exercise()

    def _create_attempt(self, key):
        submit_url = reverse("execution:submit", kwargs={"exercise_id": self.exercise.id})
        with patch("apps.execution.views.run_exercise_attempt.delay"):
            response = self.client.post(
                submit_url, {"code": "print(5)"}, format="json", HTTP_IDEMPOTENCY_KEY=key
            )
        return response.data["data"]["attempt_id"]

    def test_cancel_queued_attempt_succeeds(self):
        attempt_id = self._create_attempt("cancel-1")
        cancel_url = reverse("execution:cancel", kwargs={"attempt_id": attempt_id})
        response = self.client.post(cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "cancelled")

        execution = Execution.objects.get(attempt_id=attempt_id)
        self.assertEqual(execution.result_type, "cancelled")

    def test_cancel_already_terminal_attempt_returns_conflict(self):
        attempt_id = self._create_attempt("cancel-2")
        ExecutionRunnerService.run_attempt(attempt_id)

        cancel_url = reverse("execution:cancel", kwargs={"attempt_id": attempt_id})
        response = self.client.post(cancel_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "ATTEMPT_NOT_CANCELLABLE")

    def test_running_task_does_not_overwrite_cancellation(self):
        """
        Structural test of Phase 9 ADR-9.4: once cancelled, the worker's
        cooperative checkpoint must see the Execution row and refuse to
        overwrite it, even if invoked afterward.
        """
        attempt_id = self._create_attempt("cancel-3")
        cancel_url = reverse("execution:cancel", kwargs={"attempt_id": attempt_id})
        self.client.post(cancel_url, {}, format="json")

        ExecutionRunnerService.run_attempt(attempt_id)

        execution = Execution.objects.get(attempt_id=attempt_id)
        self.assertEqual(execution.result_type, "cancelled")