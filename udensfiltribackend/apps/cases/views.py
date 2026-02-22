from django.db.models import Prefetch
from rest_framework import viewsets, permissions
from .models import Equipment, PlumbingCase, CaseMessage
from .serializers import EquipmentSerializer, PlumbingCaseSerializer, PlumbingCaseDetailSerializer, CaseMessageSerializer
from .permissions import IsOwnerOrSuperuser

class EquipmentViewSet(viewsets.ModelViewSet):
    serializer_class=EquipmentSerializer
    permission_classes=[permissions.IsAuthenticated, IsOwnerOrSuperuser]
    def get_queryset(self):
        return Equipment.objects.all().order_by("-id") if self.request.user.is_superuser else Equipment.objects.filter(user=self.request.user).order_by("-id")
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class PlumbingCaseViewSet(viewsets.ModelViewSet):
    permission_classes=[permissions.IsAuthenticated, IsOwnerOrSuperuser]
    def get_queryset(self):
        base = PlumbingCase.objects.select_related("equipment", "user").prefetch_related(
            Prefetch("messages", queryset=CaseMessage.objects.select_related("sender").order_by("created_at"))
        )
        return base.order_by("-created_at") if self.request.user.is_superuser else base.filter(user=self.request.user).order_by("-created_at")
    def get_serializer_class(self):
        return PlumbingCaseDetailSerializer if self.action=="retrieve" else PlumbingCaseSerializer
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CaseMessageViewSet(viewsets.ModelViewSet):
    serializer_class=CaseMessageSerializer
    permission_classes=[permissions.IsAuthenticated, IsOwnerOrSuperuser]
    def get_queryset(self):
        qs = CaseMessage.objects.select_related("case","sender").all()
        return qs if self.request.user.is_superuser else qs.filter(case__user=self.request.user, is_internal=False)
    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
