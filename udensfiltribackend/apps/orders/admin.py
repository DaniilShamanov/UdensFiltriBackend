from django.contrib import admin

from .models import Order


@admin.action(description="Mark selected orders paid")
def mark_paid(modeladmin, request, queryset):
    queryset.update(status="paid")


@admin.action(description="Mark selected orders cancelled")
def mark_cancelled(modeladmin, request, queryset):
    queryset.update(status="cancelled")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "status", "total_cents", "currency", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("id", "user__phone", "user__email", "email", "stripe_session_id", "stripe_payment_intent_id")
    list_select_related = ("user",)
    readonly_fields = ("created_at", "updated_at", "stripe_session_id", "stripe_payment_intent_id")
    actions = [mark_paid, mark_cancelled]
