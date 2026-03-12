import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import EmailCode


def create_email_code(email: str, purpose: str, ttl_minutes: int = 10) -> EmailCode:
    min_interval = int(getattr(settings, "EMAIL_CODE_MIN_INTERVAL_SECONDS", 60))
    last = EmailCode.objects.filter(email=email, purpose=purpose).order_by("-created_at").first()
    if last and (timezone.now() - last.created_at).total_seconds() < min_interval:
        raise ValueError(_("Please wait before requesting a new code."))

    code = f"{random.randint(0, 999999):06d}"
    return EmailCode.objects.create(
        email=email,
        purpose=purpose,
        code=code,
        failed_attempts=0,
        locked_until=None,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )
