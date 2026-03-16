from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_invoice_email(order):
    subject = f"Your Order Confirmation #{order.id}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [order.email]

    # Prepare context for the email template
    context = {
        'order': order,
        'items': order.items,  # Assuming this is a list of dicts
        'total': order.total_cents / 100,
    }

    # Render HTML and plain text versions
    html_message = render_to_string('emails/invoice.html', context)
    plain_message = strip_tags(html_message)

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
