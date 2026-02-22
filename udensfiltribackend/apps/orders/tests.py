from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.accounts.models import BUSINESS_USERS_GROUP, GroupDiscount, User
from apps.catalog.models import Product
from apps.orders.models import Order


class StripeFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+37122000000", password="StrongPass123", email="u@example.com")
        r = self.client.post("/api/auth/login/", {"phone": self.user.phone, "password": "StrongPass123"}, format="json")
        self.client.cookies = r.cookies

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_create_checkout_session_creates_order(self, mock_create):
        mock_create.return_value = {"id": "cs_test_1", "url": "https://stripe.test/checkout"}
        product = Product.objects.create(name="Test item", slug="test-item", price_cents=1000, currency="EUR", is_active=True)
        payload = {"items": [{"product_id": product.id, "qty": 1}], "currency": "EUR"}
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Order.objects.filter(id=r.data["orderId"]).exists())

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_business_user_discount_applied(self, mock_create):
        mock_create.return_value = {"id": "cs_test_2", "url": "https://stripe.test/checkout"}
        group, _ = Group.objects.get_or_create(name=BUSINESS_USERS_GROUP)
        GroupDiscount.objects.update_or_create(group=group, defaults={"percentage": 15, "is_active": True})
        self.user.groups.add(group)

        product = Product.objects.create(name="Pump", slug="pump", price_cents=2000, currency="EUR", is_active=True)
        payload = {"items": [{"product_id": product.id, "qty": 2}], "currency": "EUR"}

        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)

        order = Order.objects.get(id=r.data["orderId"])
        self.assertEqual(order.total_cents, 3400)
        self.assertEqual(order.items[0]["discount_percent"], 15)
        self.assertEqual(order.items[0]["unit_price_cents"], 1700)

    @patch("apps.orders.views.stripe.Webhook.construct_event")
    def test_webhook_marks_paid_idempotent(self, mock_event):
        order = Order.objects.create(
            user=self.user,
            total_cents=1000,
            currency="EUR",
            items=[{"type": "product", "name": "x", "qty": 1, "unit_price_cents": 1000, "product_id": 1}],
        )
        mock_event.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_3", "payment_intent": "pi_1", "metadata": {"order_id": str(order.id)}}},
        }
        r = self.client.post("/api/orders/payments/webhook/", data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t")
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")

        r2 = self.client.post("/api/orders/payments/webhook/", data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t")
        self.assertEqual(r2.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_checkout_rejects_client_price_fields(self, mock_create):
        payload = {"items": [{"name": "Test item", "qty": 1, "unit_price_cents": 1}], "currency": "EUR"}
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        mock_create.assert_not_called()
