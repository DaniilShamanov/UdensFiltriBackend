from rest_framework import viewsets, permissions
from .models import Category, Product, Service
from .serializers import CategorySerializer, ProductSerializer, ServiceSerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes=[permissions.AllowAny]

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).order_by("name")
    serializer_class = ProductSerializer
    permission_classes=[permissions.AllowAny]
    lookup_field="slug"

class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(is_active=True).order_by("name")
    serializer_class = ServiceSerializer
    permission_classes=[permissions.AllowAny]
    lookup_field="slug"
