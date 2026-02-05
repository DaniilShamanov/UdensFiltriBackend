from django.contrib import admin
from .models import Category, Product, Service

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display=("name","slug")
    search_fields=("name","slug")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display=("name","category","price_cents","currency","is_active")
    list_filter=("is_active","category")
    search_fields=("name","slug")

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display=("name","base_price_cents","currency","is_active")
    list_filter=("is_active",)
    search_fields=("name","slug")
