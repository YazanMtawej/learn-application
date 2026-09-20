from django.urls import path

from apps.review import views

app_name = "review"

urlpatterns = [
    path("", views.ReviewStartView.as_view(), name="start"),
    path(
        "<uuid:session_id>/items/<uuid:item_id>/submit",
        views.ReviewSubmitItemView.as_view(),
        name="submit-item",
    ),
]