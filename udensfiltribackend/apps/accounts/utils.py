import random
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
import phonenumbers
from .models import SMSCode


def normalize_phone(phone: str) -> str:
    """Normalize phone numbers to E.164.

    Tailored for Latvia deployment:
    - Accepts '+371...' directly
    - Accepts local Latvian numbers (e.g., '2xxxxxxx') by parsing with region 'LV'
    """
    phone = (phone or "").strip()
    if not phone:
        raise ValueError("Phone is required")

    try:
        # If phone does not include a country code, default to Latvia.
        region = None if phone.startswith("+") else "LV"
        parsed = phonenumbers.parse(phone, region)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as exc:
        raise ValueError("Invalid phone number") from exc


def create_sms_code(phone: str, purpose: str, ttl_minutes: int = 10) -> SMSCode:
    """Create a new SMS code with basic anti-spam.

    Enforces a minimum interval between sends for the same phone/purpose.
    """
    min_interval = int(getattr(settings, "SMS_MIN_INTERVAL_SECONDS", 60))
    last = (
        SMSCode.objects.filter(phone=phone, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if last and (timezone.now() - last.created_at).total_seconds() < min_interval:
        # Keep this message generic to avoid leaking timings.
        raise ValueError("Please wait before requesting a new code")

    code = f"{random.randint(0, 999999):06d}"
    return SMSCode.objects.create(
        phone=phone,
        purpose=purpose,
        code=code,
        failed_attempts=0,
        locked_until=None,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )


def send_sms(phone: str, message: str) -> None:
    if settings.SMS_BACKEND == "console":
        print(f"[SMS to {phone}] {message}")
        return
    raise NotImplementedError("SMS backend not configured")
