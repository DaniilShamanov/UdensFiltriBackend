import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .utils import send_invoice_email
from .models import DeliveryOption, Order
from apps.catalog.models import Product
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
            delivery_option_id = int(data.get('delivery_option_id'))
        except (TypeError, ValueError):
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
        #order = ser.save()
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            email=ser.validated_data['email'],
            phone=ser.validated_data.get('phone', ''),                     # optional
            customer_name=ser.validated_data['customer_name'],
            customer_address=ser.validated_data['customer_address'],
            delivery_option=ser.validated_data['delivery_option'],         # the DeliveryOption object
            currency=ser.validated_data['currency'],
            total_cents=ser.validated_data['total_cents'],
            items=ser.validated_data['items'],                             # normalized items
            status='created',
        )

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
            'checkoutUrl': session.url,
            'orderId': order.id,
        }, status=201)

    # GET (list orders) – unchanged
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)

    qs = Order.objects.all().order_by("-created_at") if request.user.is_superuser else Order.objects.filter(user=request.user).order_by("-created_at")
    return Response(OrderSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])  # change from IsAuthenticated
def get_order(request, order_id: int):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"detail": "Not found"}, status=404)

    # If user is authenticated, check ownership
    if request.user.is_authenticated:
        if not request.user.is_superuser and order.user != request.user:
            return Response({"detail": "Permission denied"}, status=403)
    else:
        # Unauthenticated: require a valid session_id that matches the order's stripe_session_id
        session_id = request.query_params.get('session_id')
        if not session_id or order.stripe_session_id != session_id:
            return Response({"detail": "Permission denied"}, status=403)

    serializer = OrderSerializer(order)
    return Response(serializer.data)


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
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not set")
        return HttpResponse(status=500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        # Invalid payload
        logger.warning("Invalid Stripe webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        logger.warning("Invalid Stripe webhook signature")
        return HttpResponse(status=400)

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        logger.info(f"Checkout session completed: {session['id']}")

        # Extract order_id from metadata (must match what you set when creating the session)
        order_id = session.get("metadata", {}).get("order_id")
        if not order_id:
            logger.error("No order_id in session metadata")
            return HttpResponse(status=200)  # Still acknowledge receipt

        try:
            order = Order.objects.get(id=int(order_id))
        except Order.DoesNotExist:
            logger.error(f"Order with id {order_id} not found")
            return HttpResponse(status=200)  # Acknowledge but log

        # Update order status and Stripe fields
        order.status = "paid"
        order.stripe_session_id = session.get("id", "")          # store session ID if not already
        order.stripe_payment_intent_id = session.get("payment_intent", "")
        order.save(update_fields=["status", "stripe_session_id", "stripe_payment_intent_id"])

        # Send invoice email
        try:
            send_invoice_email(order)
            logger.info(f"Order {order_id} updated to paid and invoice email sent.")
        except Exception as e:
            logger.exception(f"Failed to send invoice email for order {order_id}: {e}")

    return HttpResponse(status=200)
