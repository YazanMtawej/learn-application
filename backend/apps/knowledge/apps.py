from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.knowledge"
    label = "knowledge"

    def ready(self):
        # Registers the ExerciseEvaluated event consumer (Phase 4 §13:
        # "ExerciseEvaluated | ... | Knowledge & Mastery, Gamification,
        # Adaptive Learning"). Importing here (not at module load time)
        # avoids circular imports between apps.knowledge and
        # apps.execution.
        from apps.knowledge import signals  # noqa: F401