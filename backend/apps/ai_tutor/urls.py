from django.urls import path

from apps.ai_tutor import views

app_name = "ai_tutor"

urlpatterns = [
    path("attempts/<uuid:attempt_id>/hints", views.HintRequestView.as_view(), name="hint-request"),
    path("attempts/<uuid:attempt_id>/hints/state", views.HintStateView.as_view(), name="hint-state"),
]