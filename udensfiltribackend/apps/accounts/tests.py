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

    def test_request_email_code_returns_mock_code(self):
        email = "user@example.com"
        response = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("mock_code", response.data)
        self.assertEqual(len(response.data["mock_code"]), 6)

    def test_request_email_code_blocks_registered_email_for_signup(self):
        User.objects.create_user(phone=None, email="registered@example.com", password="StrongPass123")

        response = self.client.post(
            "/api/auth/request-email-code/",
            {"purpose": "register", "email": "registered@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "This email is already registered.")

    def test_request_email_code_returns_plain_text_validation_errors(self):
        response = self.client.post(
            "/api/auth/request-email-code/",
            {"purpose": "register"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "email: Email is required.")

    def test_register_with_email_code(self):
        email = "user@example.com"
        code_response = self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        code = code_response.data["mock_code"]

        response = self.client.post(
            "/api/auth/register/",
            {"email": email, "password": "StrongPass123", "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.cookies)
        self.assertIn("refresh", response.cookies)

    def test_login_with_email_sets_cookies(self):
        User.objects.create_user(phone=None, email="u@example.com", password="StrongPass123")

        response = self.client.post("/api/auth/login/", {"email": "u@example.com", "password": "StrongPass123"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.cookies)

    def test_login_rejects_sql_injection_payload(self):
        User.objects.create_user(phone=None, email="safe@example.com", password="StrongPass123")

        response = self.client.post(
            "/api/auth/login/",
            {"email": "safe@example.com' OR 1=1 --", "password": "StrongPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertEqual(response.data["error"]["fields"]["email"][0]["code"], "invalid")

    def test_register_rejects_sql_injection_payload(self):
        code_response = self.client.post(
            "/api/auth/request-email-code/",
            {"purpose": "register", "email": "new@example.com"},
            format="json",
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com'; DROP TABLE accounts_user; --",
                "password": "StrongPass123",
                "code": code_response.data["mock_code"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_email_code_lockout_after_failed_attempts(self):
        email = "lock@example.com"
        self.client.post("/api/auth/request-email-code/", {"purpose": "register", "email": email}, format="json")
        latest = EmailCode.objects.filter(email=email, purpose="register").latest("created_at")

        for _ in range(5):
            response = self.client.post(
                "/api/auth/register/",
                {"email": email, "password": "StrongPass123", "code": "000000"},
                format="json",
            )
        self.assertIn(response.status_code, (400, 429))

        latest.refresh_from_db()
        self.assertIsNotNone(latest.locked_until)

    def test_change_phone_does_not_require_code(self):
        User.objects.create_user(phone=None, email="phone-owner@example.com", password="StrongPass123")
        self._login("phone-owner@example.com", "StrongPass123")

        response = self.client.post(
            "/api/auth/change-phone/",
            {"new_phone": "+37120000001"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["phone"], "+37120000001")

    def test_change_phone_rejects_duplicate_phone(self):
        User.objects.create_user(phone="+37120000002", email="existing@example.com", password="StrongPass123")
        User.objects.create_user(phone=None, email="phone-owner2@example.com", password="StrongPass123")
        self._login("phone-owner2@example.com", "StrongPass123")

        response = self.client.post(
            "/api/auth/change-phone/",
            {"new_phone": "+37120000002"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "phone_exists")

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


class SendGridSettingsTests(TestCase):
    @override_settings(SENDGRID_API_KEY="SG.key", EMAIL_BACKEND="config.email_backends.SendGridEmailBackend")
    def test_sendgrid_backend_is_configurable(self):
        from django.conf import settings

        self.assertEqual(settings.SENDGRID_API_KEY, "SG.key")
        self.assertEqual(settings.EMAIL_BACKEND, "config.email_backends.SendGridEmailBackend")
