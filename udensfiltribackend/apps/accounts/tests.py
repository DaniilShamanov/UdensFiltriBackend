from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import EmailCode, User


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _login(self, email: str, password: str):
        response = self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.cookies = response.cookies

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

    def test_request_email_code_sends_email_with_purpose_subject(self):
        email = "mailbox@example.com"
        r = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])
        self.assertIn("Registration confirmation code", mail.outbox[0].subject)

    @override_settings(EMAIL_CODE_MIN_INTERVAL_SECONDS=0)
    def test_change_email_and_password_use_current_email_verification(self):
        user = User.objects.create_user(phone=None, email="owner@example.com", password="StrongPass123")
        self._login("owner@example.com", "StrongPass123")

        code_request = self.client.post(
            "/api/auth/request-email-code/",
            {"purpose": "change_email", "email": "new@example.com"},
            format="json",
        )
        self.assertEqual(code_request.status_code, 200)

        code_obj = EmailCode.objects.filter(email="owner@example.com", purpose="change_email").latest("created_at")
        change_email_response = self.client.post(
            "/api/auth/change-email/",
            {"new_email": "new@example.com", "code": code_obj.code},
            format="json",
        )
        self.assertEqual(change_email_response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")

        password_code_request = self.client.post(
            "/api/auth/request-email-code/",
            {"purpose": "change_password"},
            format="json",
        )
        self.assertEqual(password_code_request.status_code, 200)

        password_code = EmailCode.objects.filter(email="new@example.com", purpose="change_password").latest("created_at").code
        change_password_response = self.client.post(
            "/api/auth/change-password/",
            {"new_password": "EvenStronger123", "code": password_code},
            format="json",
        )
        self.assertEqual(change_password_response.status_code, 200)

        relogin = self.client.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": "EvenStronger123"},
            format="json",
        )
        self.assertEqual(relogin.status_code, 200)


class SendGridSettingsTests(TestCase):
    @override_settings(SENDGRID_API_KEY="SG.key", EMAIL_BACKEND="config.email_backends.SendGridEmailBackend")
    def test_sendgrid_backend_is_configurable(self):
        from django.conf import settings

        self.assertEqual(settings.SENDGRID_API_KEY, "SG.key")
        self.assertEqual(settings.EMAIL_BACKEND, "config.email_backends.SendGridEmailBackend")
