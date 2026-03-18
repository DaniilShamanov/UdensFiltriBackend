import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .utils import send_invoice_email
from .models import DeliveryOption, Order
from .serializers import (
    CreateCheckoutSerializer,
    DeliveryOptionSerializer,
    OrderSerializer,
)

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

class OrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(["GET"])
@permission_classes([AllowAny])
def list_delivery_options(request):
    """Return all active delivery options."""
    qs = DeliveryOption.objects.filter(is_active=True).order_by("name")
    return Response(DeliveryOptionSerializer(qs, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def list_orders(request):
    """
    GET:  List orders for the authenticated user (or all for superuser).
    POST: Create an order and a Stripe Checkout Session.
    """
    if request.method == "POST":
        data = request.data.copy()

        # Get and validate delivery_option_id
        delivery_option_id = data.get('delivery_option_id')
        if not delivery_option_id:
            return Response({"error": "Delivery option is required"}, status=400)

        try:
            delivery_option_id = int(delivery_option_id)
        except (TypeError, ValueError):
            return Response({"error": "Invalid delivery option ID"}, status=400)

        data['delivery_option_id'] = delivery_option_id

        # Associate user if authenticated
        if request.user.is_authenticated:
            data['user'] = request.user.id

        # Validate with serializer
        ser = CreateCheckoutSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)

        # Create order (currency removed, phone now in validated_data)
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            email=ser.validated_data['email'],
            phone=ser.validated_data.get('phone', ''),
            customer_name=ser.validated_data['customer_name'],
            customer_address=ser.validated_data['customer_address'],
            delivery_option=ser.validated_data['delivery_option'],
            total_cents=ser.validated_data['total_cents'],
            items=ser.validated_data['items'],          # normalized items with price_cents
            status='created',
        )

        # Build Stripe line items from validated items (final discounted prices)
        line_items = []
        for item in ser.validated_data['items']:
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': item['name']},
                    'unit_amount': item['price_cents'],
                },
                'quantity': item['quantity'],
            })

        # Add delivery as a line item
        line_items.append({
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f"Delivery: {order.delivery_option.name}"},
                'unit_amount': order.delivery_option.price_cents,
            },
            'quantity': 1,
        })

        # Construct success/cancel URLs
        locale = data.get('locale', 'en')
        success_path = data.get('success_path', '/payment/status')
        cancel_path = data.get('cancel_path', '/checkout')
        base_url = settings.FRONTEND_BASE_URL.rstrip('/')
        success_url = f"{base_url}/{locale}{success_path}/{order.id}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/{locale}{cancel_path}"

        # Create Stripe session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=ser.validated_data['email'],
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

    # GET method – list orders for authenticated user
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)

    qs = Order.objects.all().order_by("-created_at")
    if not request.user.is_superuser:
        qs = qs.filter(user=request.user)

    paginator = OrderPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = OrderSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_order(request, order_id: int):
    """
    Retrieve a single order. Authenticated users see their own orders;
    unauthenticated users must provide a valid session_id query param.
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"detail": "Not found"}, status=404)

    if request.user.is_authenticated:
        if not request.user.is_superuser and order.user != request.user:
            return Response({"detail": "Permission denied"}, status=403)
    else:
        session_id = request.query_params.get('session_id')
        if not session_id or order.stripe_session_id != session_id:
            return Response({"detail": "Permission denied"}, status=403)

    serializer = OrderSerializer(order)
    return Response(serializer.data)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """Handle Stripe webhook events (e.g., checkout.session.completed)."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not set")
        return HttpResponse(status=500)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        logger.info(f"Checkout session completed: {session['id']}")

        order_id = session.get("metadata", {}).get("order_id")
        if not order_id:
            logger.error("No order_id in session metadata")
            return HttpResponse(status=200)

        try:
            order = Order.objects.get(id=int(order_id))
        except Order.DoesNotExist:
            logger.error(f"Order with id {order_id} not found")
            return HttpResponse(status=200)

        order.status = "paid"
        order.stripe_session_id = session.get("id", "")
        order.stripe_payment_intent_id = session.get("payment_intent", "")
        order.save(update_fields=["status", "stripe_session_id", "stripe_payment_intent_id"])

        try:
            send_invoice_email(order)
            logger.info(f"Order {order_id} updated to paid and invoice email sent.")
        except Exception as e:
            logger.exception(f"Failed to send invoice email for order {order_id}: {e}")

    return HttpResponse(status=200)