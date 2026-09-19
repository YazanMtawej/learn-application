from django.contrib import admin
from django.urls import include, path

from apps.subscriptions.views import PaymentWebhookView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.identity.urls", namespace="identity")),
    path("api/v1/subscriptions/", include("apps.subscriptions.urls", namespace="subscriptions")),
    path("api/v1/webhooks/payment", PaymentWebhookView.as_view(), name="payment_webhook"),
]