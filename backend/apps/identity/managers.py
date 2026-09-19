from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("A user must have at least an email or a phone number.")

        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        return self._create_user(email=email, phone=phone, password=password, **extra_fields)

    def create_superuser(self, email=None, phone=None, password=None, **extra_fields):
        from apps.identity.models import AccountStatus, Role, VerificationStatus

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("account_status", AccountStatus.ACTIVE)
        extra_fields.setdefault("verification_status", VerificationStatus.VERIFIED)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        return self._create_user(email=email, phone=phone, password=password, **extra_fields)