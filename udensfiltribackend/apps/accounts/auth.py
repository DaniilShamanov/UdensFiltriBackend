from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if raw:
            validated = self.get_validated_token(raw)
            return self.get_user(validated), validated
        return super().authenticate(request)

def set_auth_cookies(response, access: str, refresh: str):
    common = dict(
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(settings.AUTH_COOKIE_ACCESS_NAME, access, **common)
    response.set_cookie(settings.AUTH_COOKIE_REFRESH_NAME, refresh, **common)

def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
