from django.db import models
from django.conf import settings

class Equipment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="equipment")
    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200, blank=True, default="")
    model = models.CharField(max_length=200, blank=True, default="")
    serial_number = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    def __str__(self): return f"{self.name} ({self.user.phone})"

class PlumbingCase(models.Model):
    STATUS=[("new","new"),("reviewed","reviewed"),("scheduled","scheduled"),("in_progress","in_progress"),("done","done"),("closed","closed")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cases")
    equipment = models.ForeignKey(Equipment, on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS, default="new")
    priority = models.CharField(max_length=32, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"{self.title} ({self.user.phone})"

class CaseMessage(models.Model):
    case = models.ForeignKey(PlumbingCase, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="case_messages")
    message = models.TextField(blank=True, default="")
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=("created_at",)
