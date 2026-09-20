from django.urls import path

from apps.assessment import views

app_name = "assessment"

urlpatterns = [
    path("<uuid:module_id>/attempts", views.AssessmentStartView.as_view(), name="start"),
    path(
        "attempts/<uuid:attempt_id>/submit", views.AssessmentSubmitView.as_view(), name="submit"
    ),
    path(
        "attempts/<uuid:attempt_id>", views.AssessmentAttemptStatusView.as_view(), name="attempt-status"
    ),
]