from rest_framework import serializers
from .models import Category, Product, Service

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class ProductSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    wholesalePrice = serializers.SerializerMethodField()
    inStock = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.name')
    subCategory = serializers.CharField(source='sub_category', default='')
    brand = serializers.CharField(default='')
    rating = serializers.FloatField(default=0.0)
    reviews = serializers.IntegerField(default=0)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "price",
            "wholesalePrice",
            "category",
            "subCategory",
            "image_url",
            "inStock",
            "brand",
            "rating",
            "reviews",
            "is_active",
        )

    def get_price(self, obj):
        return obj.price_cents / 100 if obj.price_cents is not None else 0

    def get_wholesalePrice(self, obj):
        if hasattr(obj, 'wholesale_price_cents') and obj.wholesale_price_cents is not None:
            return obj.wholesale_price_cents / 100
        return None

    def get_inStock(self, obj):
        return getattr(obj, 'stock', 1) > 0


class ServiceSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = ("id", "name", "slug", "description", "price", "is_active")

    def get_price(self, obj):
        return obj.base_price_cents / 100 if obj.base_price_cents is not None else 0