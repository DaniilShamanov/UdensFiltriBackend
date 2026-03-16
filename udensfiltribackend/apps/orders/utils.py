import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from apps.accounts.utils import send_email

logger = logging.getLogger(__name__)

def send_invoice_email(order):
    try:
        subject = f"Your Order Confirmation #{order.id}"
        # Prepare context for templates
        context = {
            'order': order,
            'items': order.items,          # list of dicts with title, qty, unit_price_cents
            'total': order.total_cents / 100,  # convert cents to main currency unit
        }

        # Render HTML template and generate plain text version
        html_message = render_to_string('invoice.html', context)
        plain_message = strip_tags(html_message)

        # Send via the shared function from accounts.utils
        send_email(order.email, subject, html_message, plain_message)
        logger.info(f"Invoice email sent for order {order.id}")
    except Exception as e:
        logger.exception(f"Failed to send invoice email for order {order.id}: {e}")
        raise   # re-raise so caller (e.g., webhook) can handle it
