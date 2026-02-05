from rest_framework import viewsets, permissions
from .models import Post
from .serializers import PostSerializer

class PostViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=PostSerializer
    permission_classes=[permissions.AllowAny]
    lookup_field="slug"
    def get_queryset(self):
        return Post.objects.filter(status="published").order_by("-published_at","-id")
