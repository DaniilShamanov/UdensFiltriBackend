from django.conf import settings
from django.db import models


class DeliveryOption(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    price_cents = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.price_cents} {self.currency})"


class Order(models.Model):
    STATUS = [("created", "created"), ("paid", "paid"), ("cancelled", "cancelled")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    email = models.EmailField()
    phone = models.CharField(blank=True, default="")
    customer_name = models.CharField(max_length=200)
    customer_address = models.CharField(max_length=500)
    delivery_option = models.ForeignKey(DeliveryOption, on_delete=models.PROTECT, related_name="orders", null=True, blank=True)
    total_cents = models.PositiveIntegerField(default=0)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=STATUS, default="created")
    stripe_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} ({self.status})"
