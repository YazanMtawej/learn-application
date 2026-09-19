from django.urls import path

from apps.execution import views

app_name = "execution"

urlpatterns = [
    path("exercises/<uuid:exercise_id>/attempts", views.ExecutionSubmitView.as_view(), name="submit"),
    path("attempts/<uuid:attempt_id>", views.ExecutionStatusView.as_view(), name="status"),
    path("attempts/<uuid:attempt_id>/cancel", views.ExecutionCancelView.as_view(), name="cancel"),
]