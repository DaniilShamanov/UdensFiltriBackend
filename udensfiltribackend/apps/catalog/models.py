from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    def __str__(self): return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True, default="")
    price_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=8, default="EUR")
    image_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Service(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True, default="")
    base_price_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=8, default="EUR")
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name
