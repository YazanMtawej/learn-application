from django.urls import path

from apps.subscriptions import views

app_name = "subscriptions"

urlpatterns = [
    path("plans", views.PlansListView.as_view(), name="plans"),
    path("me", views.SubscriptionStateView.as_view(), name="state"),
    path("upgrade", views.SubscriptionUpgradeView.as_view(), name="upgrade"),
    path("cancel", views.SubscriptionCancelView.as_view(), name="cancel"),
]