from django.contrib import admin

from apps.subscriptions.models import Entitlement, PaymentEvent, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")


@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "feature_key", "limit_value")
    list_filter = ("plan",)
    search_fields = ("feature_key",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "status", "current_period_end", "grace_period_end", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("user__email", "user__phone")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "provider_event_id", "type", "processed_at")
    search_fields = ("provider_event_id",)
    readonly_fields = ("id", "subscription", "provider_event_id", "type", "payload_ref", "processed_at")

    def has_add_permission(self, request):
        return False