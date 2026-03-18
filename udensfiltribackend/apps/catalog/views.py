from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from .models import Category, Product, Service
from .serializers import CategorySerializer, ProductSerializer, ServiceSerializer


class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).order_by("name")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"
    pagination_class = ProductPagination

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(is_active=True).order_by("name")
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"  # Optional: if services are also accessed by ID