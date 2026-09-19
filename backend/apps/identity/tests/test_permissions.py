from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.identity.models import AccountStatus, Role, User, VerificationStatus
from apps.identity.permissions import IsAdmin, IsInstructor, IsOrganization, IsStudent
from apps.identity.services import AuthService


def _make_active_user(role, email):
    user = User.objects.create_user(email=email, password="StrongPass123!", role=role)
    user.verification_status = VerificationStatus.VERIFIED
    user.account_status = AccountStatus.ACTIVE
    user.save(update_fields=["verification_status", "account_status"])
    return user


class _StudentOnlyView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response({"data": {"ok": True}})


class _InstructorOnlyView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        return Response({"data": {"ok": True}})


class _OrganizationOnlyView(APIView):
    permission_classes = [IsOrganization]

    def get(self, request):
        return Response({"data": {"ok": True}})


class _AdminOnlyView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({"data": {"ok": True}})


class RoleBasedPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student = _make_active_user(Role.STUDENT, "student@example.com")
        self.instructor = _make_active_user(Role.INSTRUCTOR, "instructor@example.com")
        self.organization = _make_active_user(Role.ORGANIZATION, "organization@example.com")
        self.admin = _make_active_user(Role.ADMIN, "admin@example.com")

    def _access_token_for(self, user):
        return AuthService.issue_access_token(user)

    def _get(self, view_cls, user):
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self._access_token_for(user)}"
        return view_cls.as_view()(request)

    def test_student_can_access_student_only_view(self):
        response = self._get(_StudentOnlyView, self.student)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_instructor_cannot_access_student_only_view(self):
        response = self._get(_StudentOnlyView, self.instructor)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_can_access_instructor_only_view(self):
        response = self._get(_InstructorOnlyView, self.instructor)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_organization_can_access_organization_only_view(self):
        response = self._get(_OrganizationOnlyView, self.organization)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_organization_only_view(self):
        response = self._get(_OrganizationOnlyView, self.student)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_admin_only_view(self):
        response = self._get(_AdminOnlyView, self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_admin_only_view(self):
        response = self._get(_AdminOnlyView, self.student)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_rejected(self):
        request = self.factory.get("/")
        response = _StudentOnlyView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_suspended_user_denied_even_with_matching_role(self):
        self.student.account_status = AccountStatus.SUSPENDED
        self.student.save(update_fields=["account_status"])
        response = self._get(_StudentOnlyView, self.student)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)