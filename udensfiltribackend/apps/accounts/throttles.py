from rest_framework.throttling import SimpleRateThrottle


class SMSIPThrottle(SimpleRateThrottle):
    scope = "sms_ip"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SMSPhoneThrottle(SimpleRateThrottle):
    scope = "sms_phone"

    def get_cache_key(self, request, view):
        phone = (request.data.get("phone") or "").strip()
        # If purpose requires auth, phone might be empty; fall back to user phone.
        if not phone and getattr(request, "user", None) and request.user.is_authenticated:
            phone = request.user.phone
        if not phone:
            return None
        return self.cache_format % {"scope": self.scope, "ident": phone}
