from django.apps import AppConfig


class ReviewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.review"
    label = "review"

    def ready(self):
        from apps.review import signals  # noqa: F401