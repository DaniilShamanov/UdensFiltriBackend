from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register),
    path('send-code/', views.send_code),
    path("login/", views.login),
    path("refresh/", views.refresh),
    path("logout/", views.logout),
    path("me/", views.me),
    path("profile/", views.profile),
    path("change-email/", views.change_email),
    path("change-phone/", views.change_phone),
    path('reset-password/', views.reset_password),
    path("change-password/", views.change_password),
]