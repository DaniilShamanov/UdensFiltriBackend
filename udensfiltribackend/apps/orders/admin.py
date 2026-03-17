from django.contrib import admin

from .models import DeliveryOption, Order


@admin.action(description="Mark selected orders paid")
def mark_paid(modeladmin, request, queryset):
    queryset.update(status="paid")


@admin.action(description="Mark selected orders cancelled")
def mark_cancelled(modeladmin, request, queryset):
    queryset.update(status="cancelled")


@admin.register(DeliveryOption)
class DeliveryOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price_cents", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "customer_name", "status", "total_cents", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "id",
        "user__phone",
        "user__email",
        "email",
        "customer_name",
        "customer_address",
        "stripe_session_id",
        "stripe_payment_intent_id",
    )
    list_select_related = ("user", "delivery_option")
    readonly_fields = ("created_at", "updated_at", "stripe_session_id", "stripe_payment_intent_id")
    actions = [mark_paid, mark_cancelled]
