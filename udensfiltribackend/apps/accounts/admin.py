from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, SMSCode

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("-date_joined",)
    list_display = ("phone","email","is_staff","is_superuser","is_active")
    search_fields = ("phone","email")
    fieldsets = (
        (None, {"fields": ("phone","password")}),
        ("Personal info", {"fields": ("first_name","last_name","email")}),
        ("Permissions", {"fields": ("is_active","is_staff","is_superuser","groups","user_permissions")}),
        ("Important dates", {"fields": ("last_login","date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone","password1","password2","is_staff","is_superuser")}),
    )

@admin.register(SMSCode)
class SMSCodeAdmin(admin.ModelAdmin):
    list_display = ("phone","purpose","code","created_at","expires_at","consumed_at")
    list_filter = ("purpose",)
    search_fields = ("phone","code")
