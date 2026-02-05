from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display=("id","user","status","total_cents","currency","created_at")
    list_filter=("status","currency")
    search_fields=("id","user__phone","email","stripe_session_id","stripe_payment_intent_id")
