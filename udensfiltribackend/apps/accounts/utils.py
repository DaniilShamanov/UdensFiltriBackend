import random
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import phonenumbers

from .models import EmailCode


def normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        raise ValueError("Phone is required")

    try:
        region = None if phone.startswith("+") else "LV"
        parsed = phonenumbers.parse(phone, region)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as exc:
        raise ValueError("Invalid phone number") from exc


def create_email_code(email: str, purpose: str, ttl_minutes: int = 10) -> EmailCode:
    min_interval = int(getattr(settings, "EMAIL_CODE_MIN_INTERVAL_SECONDS", 60))
    last = (
        EmailCode.objects.filter(email=email, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if last and (timezone.now() - last.created_at).total_seconds() < min_interval:
        raise ValueError("Please wait before requesting a new code")

    code = f"{random.randint(0, 999999):06d}"
    return EmailCode.objects.create(
        email=email,
        purpose=purpose,
        code=code,
        failed_attempts=0,
        locked_until=None,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )


def send_verification_email(email: str, code: str) -> None:
    send_mail(
        subject="Your verification code",
        message=f"Your verification code is: {code}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
