from django.urls import path
from . import views

urlpatterns = [
    path("request-sms-code/", views.request_sms_code),
    path("register/", views.register),
    path("login/", views.login),
    path("refresh/", views.refresh),
    path("logout/", views.logout),
    path("me/", views.me),
    path("profile/", views.profile),
    path("change-email/", views.change_email),
    path("change-phone/", views.change_phone),
    path("change-password/", views.change_password),
]
