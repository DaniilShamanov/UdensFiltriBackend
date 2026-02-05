from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User

class CasesPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.u1 = User.objects.create_user(phone="+37121000000", password="StrongPass123")
        self.u2 = User.objects.create_user(phone="+37121000001", password="StrongPass123")
        r = self.client.post("/api/auth/login/", {"phone":self.u1.phone,"password":"StrongPass123"}, format="json")
        self.client.cookies = r.cookies

    def test_user_cannot_access_other_user_case(self):
        r = self.client.post("/api/cases/cases/", {"title":"Leak","description":"Kitchen leak"}, format="json")
        case_id = r.data["id"]
        c2 = APIClient()
        r2 = c2.post("/api/auth/login/", {"phone":self.u2.phone,"password":"StrongPass123"}, format="json")
        c2.cookies = r2.cookies
        r3 = c2.get(f"/api/cases/cases/{case_id}/")
        self.assertEqual(r3.status_code, 404)

    def test_internal_message_rejected_for_regular_user(self):
        r = self.client.post("/api/cases/cases/", {"title":"Leak","description":"desc"}, format="json")
        case_id = r.data["id"]
        r2 = self.client.post("/api/cases/messages/", {"case":case_id,"message":"note","is_internal":True}, format="json")
        self.assertEqual(r2.status_code, 400)
