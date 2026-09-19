from rest_framework.permissions import BasePermission

from apps.identity.models import Role


class HasRole(BasePermission):
    """
    RBAC base class (Phase 6 §6: authorization is enforced in the
    Application Layer, never inferred from UI). Subclass with
    `allowed_roles` set.
    """

    allowed_roles = ()
    message = "Your role does not permit this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and getattr(user, "is_authenticated", False)):
            return False
        if user.account_status != "active":
            return False
        return user.role in self.allowed_roles

    @classmethod
    def for_roles(cls, *roles):
        return type(
            f"HasRole_{'_'.join(roles)}",
            (HasRole,),
            {"allowed_roles": tuple(roles)},
        )


class IsStudent(HasRole):
    allowed_roles = (Role.STUDENT,)


class IsInstructor(HasRole):
    allowed_roles = (Role.INSTRUCTOR,)


class IsOrganization(HasRole):
    allowed_roles = (Role.ORGANIZATION,)


class IsAdmin(HasRole):
    allowed_roles = (Role.ADMIN,)