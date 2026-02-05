from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import csrf_cookie

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/csrf/", csrf_cookie),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/cases/", include("apps.cases.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/blog/", include("apps.blog.urls")),
]
