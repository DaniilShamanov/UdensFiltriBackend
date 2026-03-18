import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .models import EmailCode

def create_email_code(email: str, purpose: str, ttl_minutes: int = 10) -> EmailCode:
    min_interval = int(getattr(settings, "EMAIL_CODE_MIN_INTERVAL_SECONDS", 60))
    last = EmailCode.objects.filter(email=email, purpose=purpose).order_by("-created_at").first()
    if last and (timezone.now() - last.created_at).total_seconds() < min_interval:
        raise ValueError(_("Please wait before requesting a new code."))

    EmailCode.objects.filter(email=email, purpose=purpose, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )

    code = f"{random.randint(0, 999999):06d}"
    return EmailCode.objects.create(
        email=email,
        purpose=purpose,
        code=code,
        failed_attempts=0,
        locked_until=None,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )

def send_verification_email(email, code, purpose="register"):
    subject = f"Your verification code for {purpose}"
    html_content = f"""
    <p>Your verification code is: <strong>{code}</strong></p>
    <p>This code will expire in 10 minutes.</p>
    <p>If you did not request this, please ignore this email.</p>
    """
    plain_text = f"Your verification code is: {code}\n\nThis code will expire in 10 minutes."
    send_email(email, subject, html_content, plain_text)

def send_email(to_emails, subject, html_content, plain_text_content=None):
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_emails,
        subject=subject,
        html_content=html_content,
        plain_text_content=plain_text_content,
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        raise RuntimeError("Failed to send email via SendGrid.") from e
