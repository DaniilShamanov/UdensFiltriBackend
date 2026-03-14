import logging

import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .emailing import send_order_paid_email
from .models import DeliveryOption, Order
from .serializers import CreateCheckoutSerializer, DeliveryOptionSerializer, OrderSerializer

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(["GET"])
@permission_classes([AllowAny])
def list_delivery_options(request):
    qs = DeliveryOption.objects.filter(is_active=True).order_by("name")
    return Response(DeliveryOptionSerializer(qs, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def list_orders(request):
    if request.method == "POST":
        data = request.data.copy()

        # 1. Get delivery_option_id from request
        delivery_option_id = data.get('delivery_option_id')
        if not delivery_option_id:
            return Response({"error": "Delivery option is required"}, status=400)

        # Optional: verify the ID exists (the serializer's ForeignKey will also validate)
        try:
            delivery_option = DeliveryOption.objects.get(id=delivery_option_id)
        except DeliveryOption.DoesNotExist:
            return Response({"error": "Invalid delivery option ID"}, status=400)

        # 2. Set the delivery_option_id in data for serializer
        data['delivery_option_id'] = delivery_option_id

        # 3. Compute total_cents from items
        items = data.get('items', [])
        total_cents = 0
        for item in items:
            unit_price = item.get('unit_price')
            if unit_price is None:
                return Response({"error": "Each item must have unit_price"}, status=400)
            total_cents += int(unit_price * 100) * item['quantity']
        data['total_cents'] = total_cents
        data['currency'] = 'EUR'

        # 4. Associate user if authenticated
        if request.user.is_authenticated:
            data['user'] = request.user.id

        # 5. Validate and create order using serializer
        ser = CreateCheckoutSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)
        order = ser.save()

        # 6. Build Stripe line items
        line_items = []
        for item in items:
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': item['title']},
                    'unit_amount': int(item['unit_price'] * 100),
                },
                'quantity': item['quantity'],
            })

        # 7. Construct success/cancel URLs
        locale = data.get('locale', 'en')
        success_path = data.get('success_path', '/payment/status')
        cancel_path = data.get('cancel_path', '/checkout')
        base_url = settings.FRONTEND_BASE_URL.rstrip('/')
        success_url = f"{base_url}/{locale}{success_path}/{order.id}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/{locale}{cancel_path}"

        # 8. Create Stripe session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=data.get('email'),
                metadata={'order_id': str(order.id)},
            )
        except stripe.error.StripeError as e:
            order.delete()
            return Response({"error": str(e)}, status=400)

        order.stripe_session_id = session.id
        order.save(update_fields=['stripe_session_id'])

        return Response({
            'checkout_url': session.url,
            'order_id': order.id,
        }, status=201)

    # GET (list orders) – unchanged
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)

    qs = Order.objects.all().order_by("-created_at") if request.user.is_superuser else Order.objects.filter(user=request.user).order_by("-created_at")
    return Response(OrderSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order(request, order_id: int):
    try:
        order = Order.objects.get(id=order_id) if request.user.is_superuser else Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({"detail": "Not found"}, status=404)
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def create_checkout_session(request):
    ser = CreateCheckoutSerializer(data=request.data, context={"request": request})
    ser.is_valid(raise_exception=True)

    items = ser.validated_data["items"]
    total = ser.validated_data["total_cents"]
    currency = ser.validated_data.get("currency", "EUR")
    email = ser.validated_data["email"]
    customer_name = ser.validated_data["customer_name"]
    customer_address = ser.validated_data["customer_address"]
    delivery_option = ser.validated_data["delivery_option"]

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        items=items,
        total_cents=total,
        currency=currency,
        email=email,
        customer_name=customer_name,
        customer_address=customer_address,
        delivery_option=delivery_option,
    )

    line_items = [
        {
            "price_data": {
                "currency": currency.lower(),
                "product_data": {"name": it["name"]},
                "unit_amount": it["unit_price_cents"],
            },
            "quantity": it["qty"],
        }
        for it in items
    ]
    line_items.append(
        {
            "price_data": {
                "currency": currency.lower(),
                "product_data": {"name": f"Delivery: {delivery_option.name}"},
                "unit_amount": delivery_option.price_cents,
            },
            "quantity": 1,
        }
    )

    success_url = f"{settings.FRONTEND_BASE_URL}/payment/status/{order.id}?success=1"
    cancel_url = f"{settings.FRONTEND_BASE_URL}/cart?cancel=1"

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": str(order.id)},
    )
    order.stripe_session_id = session.get("id", "")
    order.save(update_fields=["stripe_session_id"])
    return Response({"orderId": order.id, "checkoutUrl": session.get("url")})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook(request):
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        logger.warning("Stripe webhook payload parse failure")
        return Response({"detail": "invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed")
        return Response({"detail": "invalid signature"}, status=400)

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        order_id = data.get("metadata", {}).get("order_id")
        session_id = data.get("id", "")
        payment_intent = data.get("payment_intent", "")
        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                if order.status != "paid":
                    order.status = "paid"
                    order.stripe_session_id = session_id or order.stripe_session_id
                    order.stripe_payment_intent_id = payment_intent or order.stripe_payment_intent_id
                    order.save(update_fields=["status", "stripe_session_id", "stripe_payment_intent_id"])
                    send_order_paid_email(order)
            except Order.DoesNotExist:
                pass
    return Response({"ok": True})
