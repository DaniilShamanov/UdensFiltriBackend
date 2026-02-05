from django.test import TestCase
from rest_framework.test import APIClient
from .models import User, SMSCode

class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_with_sms_code_phone_first(self):
        r = self.client.post("/api/auth/request-sms-code/", {"purpose":"register","phone":"+37120000000"}, format="json")
        self.assertEqual(r.status_code, 200)
        code = SMSCode.objects.filter(phone="+37120000000", purpose="register").latest("created_at").code
        r2 = self.client.post("/api/auth/register/", {"phone":"+37120000000","password":"StrongPass123","code":code}, format="json")
        self.assertEqual(r2.status_code, 201)
        self.assertIn("access", r2.cookies)
        self.assertIn("refresh", r2.cookies)
        self.assertTrue(User.objects.filter(phone="+37120000000").exists())

    def test_login_sets_cookies(self):
        User.objects.create_user(phone="+37120000001", password="StrongPass123")
        r = self.client.post("/api/auth/login/", {"phone":"+37120000001","password":"StrongPass123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.cookies)


    def test_sms_code_lockout_after_failed_attempts(self):
        # Request a code
        self.client.post("/api/auth/request-sms-code/", {"purpose":"register","phone":"+37120000009"}, format="json")
        latest = SMSCode.objects.filter(phone="+37120000009", purpose="register").latest("created_at")

        # Try wrong code 5 times -> lock
        for _ in range(5):
            r = self.client.post("/api/auth/register/", {"phone":"+37120000009","password":"StrongPass123","code":"000000"}, format="json")
        self.assertIn(r.status_code, (400, 429))

        latest.refresh_from_db()
        self.assertIsNotNone(latest.locked_until)

        # Even with correct code now -> locked
        r2 = self.client.post("/api/auth/register/", {"phone":"+37120000009","password":"StrongPass123","code":latest.code}, format="json")
        self.assertEqual(r2.status_code, 429)


    def test_sms_min_interval(self):
        r1 = self.client.post("/api/auth/request-sms-code/", {"purpose":"register","phone":"+37120000011"}, format="json")
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post("/api/auth/request-sms-code/", {"purpose":"register","phone":"+37120000011"}, format="json")
        self.assertEqual(r2.status_code, 429)
