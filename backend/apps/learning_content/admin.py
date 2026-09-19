from django.contrib import admin

from apps.learning_content.models import (
    Concept,
    Exercise,
    ExerciseConcept,
    Lesson,
    Module,
    Prerequisite,
    TestCase,
)


@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "base_difficulty")
    search_fields = ("name",)


@admin.register(Prerequisite)
class PrerequisiteAdmin(admin.ModelAdmin):
    list_display = ("id", "source_concept", "target_concept", "mastery_threshold")
    list_filter = ("source_concept", "target_concept")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "order_index")
    ordering = ("order_index",)


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("objective", "order_index", "concept")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("id", "module", "concept", "order_index")
    list_filter = ("module",)


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 0


class ExerciseConceptInline(admin.TabularInline):
    model = ExerciseConcept
    extra = 0


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "type", "difficulty", "lifecycle_status")
    list_filter = ("type", "lifecycle_status")
    inlines = [TestCaseInline, ExerciseConceptInline]
    readonly_fields = ("id",)


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "exercise", "visibility")
    list_filter = ("visibility",)