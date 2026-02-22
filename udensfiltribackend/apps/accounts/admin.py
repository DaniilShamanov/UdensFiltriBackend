from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group

from .models import (
    BUSINESS_USERS_GROUP,
    REGULAR_USERS_GROUP,
    EmailCode,
    GroupDiscount,
    User,
)


@admin.action(description="Assign selected users to regular_users")
def assign_regular_users(modeladmin, request, queryset):
    regular_group, _ = Group.objects.get_or_create(name=REGULAR_USERS_GROUP)
    business_group, _ = Group.objects.get_or_create(name=BUSINESS_USERS_GROUP)
    for user in queryset:
        user.groups.remove(business_group)
        user.groups.add(regular_group)


@admin.action(description="Assign selected users to business_users")
def assign_business_users(modeladmin, request, queryset):
    regular_group, _ = Group.objects.get_or_create(name=REGULAR_USERS_GROUP)
    business_group, _ = Group.objects.get_or_create(name=BUSINESS_USERS_GROUP)
    for user in queryset:
        user.groups.remove(regular_group)
        user.groups.add(business_group)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("-date_joined",)
    list_display = ("phone", "email", "is_staff", "is_superuser", "is_active", "user_groups")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("phone", "email", "first_name", "last_name")
    actions = [assign_regular_users, assign_business_users]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "email", "password1", "password2", "is_staff", "is_superuser")}),
    )

    def user_groups(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or "-"


@admin.register(GroupDiscount)
class GroupDiscountAdmin(admin.ModelAdmin):
    list_display = ("group", "percentage", "is_active", "updated_at")
    list_filter = ("is_active", "group")
    search_fields = ("group__name",)


@admin.register(EmailCode)
class EmailCodeAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "code", "created_at", "expires_at", "consumed_at")
    list_filter = ("purpose",)
    search_fields = ("email", "code")
