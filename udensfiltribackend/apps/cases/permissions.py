from rest_framework.permissions import BasePermission

class IsOwnerOrSuperuser(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated and request.user.is_superuser:
            return True
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "case"):
            owner = obj.case.user
        return request.user.is_authenticated and owner == request.user
