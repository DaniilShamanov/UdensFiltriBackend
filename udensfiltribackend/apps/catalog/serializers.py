from rest_framework import serializers
from .models import Category, Product, Service

class CategorySerializer(serializers.ModelSerializer):
    class Meta: model=Category; fields=("id","name","slug")

class ProductSerializer(serializers.ModelSerializer):
    class Meta: model=Product; fields=("id","name","slug","description","price_cents","currency","image_url","category","is_active")

class ServiceSerializer(serializers.ModelSerializer):
    class Meta: model=Service; fields=("id","name","slug","description","base_price_cents","currency","is_active")
