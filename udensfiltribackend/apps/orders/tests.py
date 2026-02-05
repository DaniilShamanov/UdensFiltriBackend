from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from apps.accounts.models import User
from apps.orders.models import Order

class StripeFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+37122000000", password="StrongPass123", email="u@example.com")
        r = self.client.post("/api/auth/login/", {"phone":self.user.phone,"password":"StrongPass123"}, format="json")
        self.client.cookies = r.cookies

    @patch("apps.orders.views.stripe.checkout.Session.create")
    def test_create_checkout_session_creates_order(self, mock_create):
        mock_create.return_value = {"id":"cs_test_1","url":"https://stripe.test/checkout"}
        payload = {"items":[{"name":"Test item","qty":1,"unit_price_cents":1000}],"currency":"EUR"}
        r = self.client.post("/api/orders/payments/create-checkout-session/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Order.objects.filter(id=r.data["orderId"]).exists())

    @patch("apps.orders.views.stripe.Webhook.construct_event")
    def test_webhook_marks_paid_idempotent(self, mock_event):
        order = Order.objects.create(user=self.user, total_cents=1000, currency="EUR", items=[{"name":"x","qty":1,"unit_price_cents":1000}])
        mock_event.return_value = {
            "type":"checkout.session.completed",
            "data":{"object":{"id":"cs_test_2","payment_intent":"pi_1","metadata":{"order_id":str(order.id)}}}
        }
        r = self.client.post("/api/orders/payments/webhook/", data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t")
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        # second call stays paid
        r2 = self.client.post("/api/orders/payments/webhook/", data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t")
        self.assertEqual(r2.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
