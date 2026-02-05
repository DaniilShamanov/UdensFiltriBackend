from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def send_order_paid_email(order):
    recipient = order.email or getattr(order.user, "email", None)
    if not recipient:
        return False
    subject = f"Payment received for Order #{order.id}"
    ctx = {"order": order}
    text = render_to_string("orders/email_order_paid.txt", ctx)
    html = render_to_string("orders/email_order_paid.html", ctx)
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [recipient])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)

    if settings.ADMIN_NOTIFICATION_EMAILS:
        admin_subject = f"[Admin] Order #{order.id} paid"
        admin_text = render_to_string("orders/email_order_paid_admin.txt", ctx)
        admin_html = render_to_string("orders/email_order_paid_admin.html", ctx)
        admin_msg = EmailMultiAlternatives(admin_subject, admin_text, settings.DEFAULT_FROM_EMAIL, settings.ADMIN_NOTIFICATION_EMAILS)
        admin_msg.attach_alternative(admin_html, "text/html")
        admin_msg.send(fail_silently=True)
    return True
