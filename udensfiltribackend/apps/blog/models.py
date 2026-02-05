from django.db import models
from django.utils import timezone

class Post(models.Model):
    STATUS=[("draft","draft"),("published","published")]
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=270, unique=True)
    excerpt = models.TextField(blank=True, default="")
    body = models.TextField(blank=True, default="")
    cover_image_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS, default="draft")
    published_at = models.DateTimeField(blank=True, null=True)
    meta_title = models.CharField(max_length=250, blank=True, default="")
    meta_description = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def publish(self):
        self.status="published"
        if not self.published_at:
            self.published_at = timezone.now()
        self.save()

    def __str__(self): return self.title
