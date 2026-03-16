from django.urls import path

from . import views

urlpatterns = [
    path("", views.list_orders),
    path("<int:order_id>/", views.get_order),
    path("delivery-options/", views.list_delivery_options),
    path("payments/create-checkout-session/", views.create_checkout_session),
    path("payments/webhook/", views.stripe_webhook),
]
