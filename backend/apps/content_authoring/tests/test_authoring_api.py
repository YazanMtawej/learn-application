from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.content_authoring.models import ContentDraft
from apps.identity.models import AccountStatus, Role, User, VerificationStatus
from apps.identity.services import AuthService
from apps.learning_content.models import Concept, Exercise, Lesson, Module


def _active_client(email, role=Role.STUDENT):
    user = User.objects.create_user(email=email, password="StrongPass123!", role=role)
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])

    client = APIClient()
    access_token = AuthService.issue_access_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, user


class ContentDraftCreateAuthorizationTests(TestCase):
    def setUp(self):
        self.url = reverse("content_authoring:draft-create")

    def test_admin_can_create_draft(self):
        client, _ = _active_client("admin1@example.com", role=Role.ADMIN)
        response = client.post(
            self.url, {"content_type": "lesson", "payload": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_student_forbidden_from_creating_draft(self):
        client, _ = _active_client("student1@example.com", role=Role.STUDENT)
        response = client.post(
            self.url, {"content_type": "lesson", "payload": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_forbidden_from_creating_draft(self):
        client, _ = _active_client("instructor1@example.com", role=Role.INSTRUCTOR)
        response = client.post(
            self.url, {"content_type": "lesson", "payload": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected(self):
        anonymous_client = APIClient()
        response = anonymous_client.post(
            self.url, {"content_type": "lesson", "payload": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_content_type_rejected_at_serializer_level(self):
        client, _ = _active_client("admin2@example.com", role=Role.ADMIN)
        response = client.post(
            self.url, {"content_type": "project", "payload": {}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LessonPublishTests(TestCase):
    def setUp(self):
        self.create_url = reverse("content_authoring:draft-create")
        self.admin_client, self.admin_user = _active_client("adminlesson@example.com", role=Role.ADMIN)
        self.module = Module.objects.create(title="Fundamentals", order_index=1)

    def _publish_url(self, draft_id):
        return reverse("content_authoring:draft-publish", kwargs={"draft_id": draft_id})

    def test_successful_lesson_publish_creates_lesson_row(self):
        create_response = self.admin_client.post(
            self.create_url,
            {
                "content_type": "lesson",
                "payload": {
                    "module_id": str(self.module.id),
                    "objective": "Understand variables",
                    "content_ref": "ref://variables",
                    "order_index": 1,
                },
            },
            format="json",
        )
        draft_id = create_response.data["data"]["id"]

        publish_response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(publish_response.data["data"]["status"], "published")
        self.assertIsNotNone(publish_response.data["data"]["published_lesson"])

        self.assertEqual(Lesson.objects.filter(module=self.module).count(), 1)

    def test_publish_missing_required_field_returns_validation_failed(self):
        create_response = self.admin_client.post(
            self.create_url,
            {"content_type": "lesson", "payload": {"objective": "Missing module"}},
            format="json",
        )
        draft_id = create_response.data["data"]["id"]

        publish_response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(publish_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(publish_response.data["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(Lesson.objects.count(), 0)

    def test_republishing_already_published_draft_returns_conflict(self):
        create_response = self.admin_client.post(
            self.create_url,
            {
                "content_type": "lesson",
                "payload": {
                    "module_id": str(self.module.id),
                    "objective": "Understand loops",
                    "content_ref": "ref://loops",
                    "order_index": 2,
                },
            },
            format="json",
        )
        draft_id = create_response.data["data"]["id"]
        self.admin_client.post(self._publish_url(draft_id), {}, format="json")

        second_response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second_response.data["error"]["code"], "DRAFT_ALREADY_PUBLISHED")

    def test_publish_unknown_draft_returns_not_found(self):
        response = self.admin_client.post(
            self._publish_url("00000000-0000-0000-0000-000000000000"), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "CONTENT_DRAFT_NOT_FOUND")

    def test_student_cannot_publish(self):
        create_response = self.admin_client.post(
            self.create_url,
            {
                "content_type": "lesson",
                "payload": {
                    "module_id": str(self.module.id),
                    "objective": "x",
                    "content_ref": "ref://x",
                    "order_index": 3,
                },
            },
            format="json",
        )
        draft_id = create_response.data["data"]["id"]

        student_client, _ = _active_client("studentpublish@example.com", role=Role.STUDENT)
        response = student_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ExercisePublishTests(TestCase):
    def setUp(self):
        self.create_url = reverse("content_authoring:draft-create")
        self.admin_client, self.admin_user = _active_client("adminexercise@example.com", role=Role.ADMIN)
        module = Module.objects.create(title="Fundamentals", order_index=10)
        self.lesson = Lesson.objects.create(
            module=module, objective="Intro", content_ref="ref://intro", order_index=1
        )
        self.concept = Concept.objects.create(name="Loops", base_difficulty=2)

    def _publish_url(self, draft_id):
        return reverse("content_authoring:draft-publish", kwargs={"draft_id": draft_id})

    def _create_draft(self, payload):
        response = self.admin_client.post(
            self.create_url, {"content_type": "exercise", "payload": payload}, format="json"
        )
        return response.data["data"]["id"]

    def test_code_writing_exercise_without_hidden_test_case_fails_validation(self):
        draft_id = self._create_draft(
            {
                "lesson_id": str(self.lesson.id),
                "type": "code_writing",
                "difficulty": 2,
                "concept_ids": [str(self.concept.id)],
                "test_cases": [
                    {"input": "1", "expected_output": "1", "visibility": "visible"},
                ],
            }
        )
        response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(Exercise.objects.count(), 0)

    def test_code_writing_exercise_with_visible_and_hidden_publishes_successfully(self):
        draft_id = self._create_draft(
            {
                "lesson_id": str(self.lesson.id),
                "type": "code_writing",
                "difficulty": 2,
                "concept_ids": [str(self.concept.id)],
                "test_cases": [
                    {"input": "1", "expected_output": "1", "visibility": "visible"},
                    {"input": "2", "expected_output": "2", "visibility": "hidden"},
                ],
            }
        )
        response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exercise = Exercise.objects.get()
        self.assertEqual(exercise.lifecycle_status, "published")
        self.assertEqual(exercise.test_cases.count(), 2)
        self.assertEqual(exercise.concepts.count(), 1)

    def test_mcq_exercise_without_hidden_test_case_publishes_successfully(self):
        draft_id = self._create_draft(
            {
                "lesson_id": str(self.lesson.id),
                "type": "mcq",
                "difficulty": 1,
                "concept_ids": [str(self.concept.id)],
                "test_cases": [
                    {"input": "A", "expected_output": "A", "visibility": "visible"},
                ],
            }
        )
        response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Exercise.objects.count(), 1)

    def test_exercise_with_nonexistent_concept_id_fails_validation(self):
        draft_id = self._create_draft(
            {
                "lesson_id": str(self.lesson.id),
                "type": "mcq",
                "difficulty": 1,
                "concept_ids": ["00000000-0000-0000-0000-000000000000"],
                "test_cases": [
                    {"input": "A", "expected_output": "A", "visibility": "visible"},
                ],
            }
        )
        response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Exercise.objects.count(), 0)

    def test_exercise_with_no_test_cases_fails_validation(self):
        draft_id = self._create_draft(
            {
                "lesson_id": str(self.lesson.id),
                "type": "mcq",
                "difficulty": 1,
                "concept_ids": [str(self.concept.id)],
                "test_cases": [],
            }
        )
        response = self.admin_client.post(self._publish_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)