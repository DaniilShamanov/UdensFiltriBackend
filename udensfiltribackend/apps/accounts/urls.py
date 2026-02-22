from django.urls import path
from . import views
from .views import CookieTokenRefreshView

urlpatterns = [
    path("request-email-code/", views.request_email_code),
    path("request-sms-code/", views.request_email_code),
    path("register/", views.register),
    path("login/", views.login),
    path("refresh/", views.refresh),
    path("logout/", views.logout),
    path("me/", views.me),
    path("profile/", views.profile),
    path("change-email/", views.change_email),
    path("change-phone/", views.change_phone),
    path("change-password/", views.change_password),
    path('api/auth/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
]
