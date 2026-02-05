from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model=Post
        fields=("id","title","slug","excerpt","body","cover_image_url","published_at","meta_title","meta_description")
