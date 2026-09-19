import uuid

from django.db import IntegrityError
from django.test import TestCase

from apps.content_authoring.models import ContentDraft
from apps.identity.models import User


class ContentDraftModelTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="author@example.com", password="StrongPass123!")

    def test_invalid_content_type_rejected_by_constraint(self):
        draft = ContentDraft.objects.create(
            author=self.author, content_type="lesson", payload={"objective": "x"}
        )
        draft.content_type = "not_a_real_type"
        with self.assertRaises(IntegrityError):
            draft.save()

    def test_invalid_status_rejected_by_constraint(self):
        draft = ContentDraft.objects.create(
            author=self.author, content_type="lesson", payload={"objective": "x"}
        )
        draft.status = "not_a_real_status"
        with self.assertRaises(IntegrityError):
            draft.save()

    def test_default_status_is_draft(self):
        draft = ContentDraft.objects.create(
            author=self.author, content_type="exercise", payload={}
        )
        self.assertEqual(draft.status, "draft")