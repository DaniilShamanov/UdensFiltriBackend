from rest_framework.throttling import SimpleRateThrottle


class CodeIPThrottle(SimpleRateThrottle):
    scope = "code_ip"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class CodeEmailThrottle(SimpleRateThrottle):
    scope = "code_email"

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        if not email and getattr(request, "user", None) and request.user.is_authenticated:
            email = (request.user.email or "").lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}
