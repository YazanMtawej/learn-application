from django.urls import path

from apps.adaptive import views

app_name = "adaptive"

urlpatterns = [
    path("current", views.AdaptiveCurrentView.as_view(), name="current"),
]