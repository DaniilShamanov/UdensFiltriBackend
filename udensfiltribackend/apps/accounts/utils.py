import random
from datetime import timedelta
from dotenv import load_dotenv

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .models import EmailCode

load_dotenv()

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

def send_verification_code_email(email, code, purpose="register"):
    subject = f"Your verification code for {purpose}"
    html_content = f"""
    <p>Your verification code is: <strong>{code}</strong></p>
    <p>This code will expire in 10 minutes.</p>
    <p>If you did not request this, please ignore this email.</p>
    """
    plain_text = f"Your verification code is: {code}\n\nThis code will expire in 10 minutes."
    send_email(email, subject, html_content, plain_text)

def send_invoice_email(order):
    subject = f"Your Invoice for Order #{order.id}"
    context = {
        'order': order,
        'items': order.items,  # list of dicts with title, qty, unit_price_cents
        'total': order.total_cents / 100,  # for convenience
    }
    html_body = render_to_string('emails/invoice.html', context)
    text_body = render_to_string('emails/invoice.txt', context)
    send_email(order.email, subject, html_body, text_body)

def send_email(to_emails, subject, html_content, plain_text_content=None):
    """
    Generic function to send an email via SendGrid Web API.
    """
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
        # Log response status for debugging
        print(f"SendGrid response status: {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"SendGrid error: {e}")
        raise  # Re-raise to handle in caller

# delete later
def send_verification_email(email, code, purpose):
    subject = f"Your verification code for {purpose}"
    html_content = f"<p>Your code is: <strong>{code}</strong></p><p>It expires in 10 minutes.</p>"
    plain_text = f"Your code is: {code}\n\nIt expires in 10 minutes."
    send_email(email, subject, html_content, plain_text)