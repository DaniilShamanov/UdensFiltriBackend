from rest_framework.routers import DefaultRouter
from .views import EquipmentViewSet, PlumbingCaseViewSet, CaseMessageViewSet

router=DefaultRouter()
router.register("equipment", EquipmentViewSet, basename="equipment")
router.register("cases", PlumbingCaseViewSet, basename="cases")
router.register("messages", CaseMessageViewSet, basename="messages")
urlpatterns = router.urls
