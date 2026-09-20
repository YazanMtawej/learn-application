from django.contrib import admin
from django.urls import include, path

from apps.subscriptions.views import PaymentWebhookView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.identity.urls", namespace="identity")),
    path("api/v1/subscriptions/", include("apps.subscriptions.urls", namespace="subscriptions")),
    path("api/v1/webhooks/payment", PaymentWebhookView.as_view(), name="payment_webhook"),
    path("api/v1/content/", include("apps.content_authoring.urls", namespace="content_authoring")),
    path("api/v1/", include("apps.execution.urls", namespace="execution")),
    path("api/v1/", include("apps.ai_tutor.urls", namespace="ai_tutor")),
    path("api/v1/knowledge/", include("apps.knowledge.urls", namespace="knowledge")),
    path("api/v1/learning-path/", include("apps.adaptive.urls", namespace="adaptive")),
    path("api/v1/reviews/", include("apps.review.urls", namespace="review")),
    path("api/v1/assessments/", include("apps.assessment.urls", namespace="assessment")),
]