from django.db import models
from django.conf import settings

class Order(models.Model):
    STATUS=[("created","created"),("paid","paid"),("cancelled","cancelled")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    email = models.EmailField(blank=True, null=True)
    currency = models.CharField(max_length=8, default="EUR")
    total_cents = models.PositiveIntegerField(default=0)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=STATUS, default="created")
    stripe_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"Order #{self.id} ({self.status})"
