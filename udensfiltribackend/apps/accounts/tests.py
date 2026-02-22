from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from .models import EmailCode, User


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_with_email_code_and_optional_phone(self):
        email = "user@example.com"
        r = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        self.assertEqual(r.status_code, 200)

        code = EmailCode.objects.filter(email=email, purpose="register").latest("created_at").code
        r2 = self.client.post(
            "/api/auth/register/",
            {"email": email, "password": "StrongPass123", "code": code},
            format="json",
        )
        self.assertEqual(r2.status_code, 201)
        self.assertIn("access", r2.cookies)
        self.assertIn("refresh", r2.cookies)

        user = User.objects.get(email=email)
        self.assertIsNone(user.phone)

    def test_login_with_email_sets_cookies(self):
        user = User.objects.create_user(phone=None, email="u@example.com", password="StrongPass123")
        self.assertIsNotNone(user.pk)

        r = self.client.post("/api/auth/login/", {"email": "u@example.com", "password": "StrongPass123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.cookies)

    def test_email_code_lockout_after_failed_attempts(self):
        email = "lock@example.com"
        self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        latest = EmailCode.objects.filter(email=email, purpose="register").latest("created_at")

        for _ in range(5):
            r = self.client.post(
                "/api/auth/register/",
                {"email": email, "password": "StrongPass123", "code": "000000"},
                format="json",
            )
        self.assertIn(r.status_code, (400, 429))

        latest.refresh_from_db()
        self.assertIsNotNone(latest.locked_until)

        r2 = self.client.post(
            "/api/auth/register/",
            {"email": email, "password": "StrongPass123", "code": latest.code},
            format="json",
        )
        self.assertEqual(r2.status_code, 429)

    def test_email_code_min_interval(self):
        email = "rate@example.com"
        r1 = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        self.assertEqual(r2.status_code, 429)

    def test_request_email_code_sends_email(self):
        email = "mailbox@example.com"
        r = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])
