from django.urls import path

from apps.content_authoring import views

app_name = "content_authoring"

urlpatterns = [
    path("drafts", views.ContentDraftCreateView.as_view(), name="draft-create"),
    path("drafts/<uuid:draft_id>/publish", views.ContentDraftPublishView.as_view(), name="draft-publish"),
]