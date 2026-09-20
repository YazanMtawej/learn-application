from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.assessment"
    label = "assessment"

    def ready(self):
        from apps.assessment import signals  # noqa: F401