from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import BUSINESS_USERS_GROUP, GroupDiscount, User
from apps.catalog.models import Product
from apps.orders.models import DeliveryOption, Order


class StripeFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+37122000000", password="StrongPass123", email="u@example.com")
        self.delivery = DeliveryOption.objects.create(name="Courier", price_cents=500, currency="EUR", is_active=True)

    def _auth_client(self):
        r = self.client.post("/api/auth/login/", {"phone": self.user.phone, "password": "StrongPass123"}, format="json")
        self.client.cookies = r.cookies

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_create_checkout_session_creates_order(self, mock_create):
        self._auth_client()
        mock_create.return_value = {"id": "cs_test_1", "url": "https://stripe.test/checkout"}
        product = Product.objects.create(name="Test item", slug="test-item", price_cents=1000, currency="EUR", is_active=True)
        payload = {
            "items": [{"product_id": product.id, "qty": 1}],
            "currency": "EUR",
            "email": "buyer@example.com",
            "customer_name": "Buyer",
            "customer_address": "Riga, Testa iela 1",
            "delivery_option_id": self.delivery.id,
        }
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        order = Order.objects.get(id=r.data["orderId"])
        self.assertEqual(order.total_cents, 1500)
        self.assertEqual(order.delivery_option, self.delivery)

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_guest_checkout_allowed(self, mock_create):
        mock_create.return_value = {"id": "cs_test_guest", "url": "https://stripe.test/checkout"}
        product = Product.objects.create(name="Guest item", slug="guest-item", price_cents=1200, currency="EUR", is_active=True)
        payload = {
            "items": [{"product_id": product.id, "qty": 1}],
            "currency": "EUR",
            "email": "guest@example.com",
            "customer_name": "Guest",
            "customer_address": "Riga, Brivibas 10",
            "delivery_option_id": self.delivery.id,
        }
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        order = Order.objects.get(id=r.data["orderId"])
        self.assertIsNone(order.user)

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_business_user_discount_applied(self, mock_create):
        self._auth_client()
        mock_create.return_value = {"id": "cs_test_2", "url": "https://stripe.test/checkout"}
        group, _ = Group.objects.get_or_create(name=BUSINESS_USERS_GROUP)
        GroupDiscount.objects.update_or_create(group=group, defaults={"percentage": 15, "is_active": True})
        self.user.groups.add(group)

        product = Product.objects.create(name="Pump", slug="pump", price_cents=2000, currency="EUR", is_active=True)
        payload = {
            "items": [{"product_id": product.id, "qty": 2}],
            "currency": "EUR",
            "email": "u@example.com",
            "customer_name": "User",
            "customer_address": "Riga",
            "delivery_option_id": self.delivery.id,
        }

        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)

        order = Order.objects.get(id=r.data["orderId"])
        self.assertEqual(order.total_cents, 3900)
        self.assertEqual(order.items[0]["discount_percent"], 15)
        self.assertEqual(order.items[0]["unit_price_cents"], 1700)

    @patch("apps.orders.views.stripe.Webhook.construct_event")
    def test_webhook_marks_paid_idempotent(self, mock_event):
        order = Order.objects.create(
            user=self.user,
            email="u@example.com",
            customer_name="U",
            customer_address="A",
            total_cents=1000,
            currency="EUR",
            delivery_option=self.delivery,
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
        payload = {
            "items": [{"name": "Test item", "qty": 1, "unit_price_cents": 1}],
            "currency": "EUR",
            "email": "u@example.com",
            "customer_name": "U",
            "customer_address": "A",
            "delivery_option_id": self.delivery.id,
        }
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        mock_create.assert_not_called()


    def test_create_order_endpoint_creates_order(self):
        product = Product.objects.create(name="Direct order item", slug="direct-order-item", price_cents=900, currency="EUR", is_active=True)
        payload = {
            "items": [{"product_id": product.id, "qty": 2}],
            "currency": "EUR",
            "email": "direct@example.com",
            "customer_name": "Direct Buyer",
            "customer_address": "Riga, Brivibas 11",
            "delivery_option_id": self.delivery.id,
        }

        r = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "created")
        self.assertEqual(r.data["total_cents"], 2300)
        self.assertEqual(Order.objects.filter(email="direct@example.com").count(), 1)

    def test_get_orders_requires_authentication(self):
        r = self.client.get("/api/orders/")
        self.assertEqual(r.status_code, 401)

    def test_lists_delivery_options(self):
        r = self.client.get("/api/orders/delivery-options/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
