from django.contrib import admin

from .models import Category, Product, Service


@admin.action(description="Mark selected products active")
def mark_products_active(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.action(description="Mark selected products inactive")
def mark_products_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description="Mark selected services active")
def mark_services_active(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.action(description="Mark selected services inactive")
def mark_services_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "price_cents", "currency", "is_active")
    list_filter = ("is_active", "category", "currency")
    search_fields = ("name", "slug", "description")
    list_select_related = ("category",)
    prepopulated_fields = {"slug": ("name",)}
    actions = [mark_products_active, mark_products_inactive]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "base_price_cents", "currency", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    actions = [mark_services_active, mark_services_inactive]
