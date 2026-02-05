import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Order
from .serializers import CreateCheckoutSerializer, OrderSerializer
from .emailing import send_order_paid_email

stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_orders(request):
    qs = Order.objects.all().order_by("-created_at") if request.user.is_superuser else Order.objects.filter(user=request.user).order_by("-created_at")
    return Response(OrderSerializer(qs, many=True).data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order(request, order_id: int):
    try:
        order = Order.objects.get(id=order_id) if request.user.is_superuser else Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({"detail":"Not found"}, status=404)
    return Response(OrderSerializer(order).data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    ser = CreateCheckoutSerializer(data=request.data, context={"request": request})
    ser.is_valid(raise_exception=True)
    items = ser.validated_data["items"]
    total = ser.context["total_cents"]
    currency = ser.validated_data.get("currency","EUR")
    email = ser.validated_data.get("email") or getattr(request.user, "email", None) or None

    order = Order.objects.create(user=request.user, items=items, total_cents=total, currency=currency, email=email)

    line_items = [{
        "price_data": {
            "currency": currency.lower(),
            "product_data": {"name": it["name"]},
            "unit_amount": it["unit_price_cents"],
        },
        "quantity": it["qty"],
    } for it in items]

    success_url = f"{settings.FRONTEND_BASE_URL}/payment/status/{order.id}?success=1"
    cancel_url = f"{settings.FRONTEND_BASE_URL}/cart?cancel=1"

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": str(order.id)},
    )
    order.stripe_session_id = session.get("id","")
    order.save(update_fields=["stripe_session_id"])
    return Response({"orderId": order.id, "checkoutUrl": session.get("url")})

@csrf_exempt
@api_view(["POST"])
def webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE","")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        return Response({"detail":"invalid"}, status=400)

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        order_id = data.get("metadata", {}).get("order_id")
        session_id = data.get("id","")
        payment_intent = data.get("payment_intent","")
        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                if order.status != "paid":
                    order.status = "paid"
                    order.stripe_session_id = session_id or order.stripe_session_id
                    order.stripe_payment_intent_id = payment_intent or order.stripe_payment_intent_id
                    order.save(update_fields=["status","stripe_session_id","stripe_payment_intent_id"])
                    send_order_paid_email(order)
            except Order.DoesNotExist:
                pass
    return Response({"ok": True})
