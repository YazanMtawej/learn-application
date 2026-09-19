from django.urls import path

from apps.knowledge import views

app_name = "knowledge"

urlpatterns = [
    path("mastery", views.MasteryReadView.as_view(), name="mastery-read"),
    path("flaw-log", views.FlawLogReadView.as_view(), name="flaw-log-read"),
]