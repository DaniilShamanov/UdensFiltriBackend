from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ServiceViewSet

router=DefaultRouter()
router.register("categories", CategoryViewSet, basename="categories")
router.register("products", ProductViewSet, basename="products")
router.register("services", ServiceViewSet, basename="services")

urlpatterns = router.urls
