from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .serializers import (
    RequestSMSCodeSerializer, RegisterSerializer, LoginSerializer,
    UserSerializer, ProfileUpdateSerializer,
    ChangeEmailSerializer, ChangePhoneSerializer, ChangePasswordSerializer
)
from .models import SMSCode, User
from .utils import create_sms_code, send_sms, normalize_phone
from .auth import set_auth_cookies, clear_auth_cookies
from .throttles import SMSIPThrottle, SMSPhoneThrottle


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_cookie(request):
    token = get_token(request)
    return JsonResponse({"csrfToken": token})


def _issue_tokens(user: User):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


from typing import Optional


def _get_latest_active_code(phone: str, purpose: str) -> Optional[SMSCode]:
    return (
        SMSCode.objects.filter(phone=phone, purpose=purpose, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )


def _verify_and_consume_code(phone: str, purpose: str, code: str):
    """Verify and consume the latest active code.

    Adds basic lockout after too many wrong attempts to reduce brute forcing.
    """
    obj = _get_latest_active_code(phone, purpose)
    if not obj:
        return False, "missing"
    if timezone.now() >= obj.expires_at:
        return False, "expired"
    if obj.is_locked:
        return False, "locked"
    if obj.code != code:
        obj.failed_attempts += 1
        # Lock for 15 minutes after 5 failed attempts.
        if obj.failed_attempts >= 5:
            obj.locked_until = timezone.now() + timedelta(minutes=15)
        obj.save(update_fields=["failed_attempts", "locked_until"])
        return False, "invalid"
    obj.consume()
    return True, "ok"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([SMSIPThrottle, SMSPhoneThrottle])
def request_sms_code(request):
    ser = RequestSMSCodeSerializer(data=request.data, context={"request": request})
    ser.is_valid(raise_exception=True)
    phone = ser.validated_data["phone"]
    purpose = ser.validated_data["purpose"]
    try:
        sms = create_sms_code(phone, purpose)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=429)
    send_sms(phone, f"Your verification code is: {sms.code}")
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    phone = ser.validated_data["phone"]
    ok, reason = _verify_and_consume_code(phone, "register", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return Response({"detail": "Invalid or expired code"}, status=status_code)

    user = User.objects.create_user(
        phone=phone,
        password=ser.validated_data["password"],
        email=ser.validated_data.get("email") or None,
        first_name=ser.validated_data.get("first_name", ""),
        last_name=ser.validated_data.get("last_name", ""),
    )
    access, refresh = _issue_tokens(user)
    resp = Response({"user": UserSerializer(user).data}, status=201)
    set_auth_cookies(resp, access, refresh)
    return resp


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    ser = LoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.validated_data["user"]
    access, refresh = _issue_tokens(user)
    resp = Response({"user": UserSerializer(user).data})
    set_auth_cookies(resp, access, refresh)
    return resp


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    refresh_cookie = request.COOKIES.get("refresh")
    if not refresh_cookie:
        return Response({"detail": "No refresh cookie"}, status=401)
    try:
        token = RefreshToken(refresh_cookie)
        new_access = str(token.access_token)
        new_refresh = str(token)  # rotate by default in SIMPLE_JWT
        resp = Response({"ok": True})
        set_auth_cookies(resp, new_access, new_refresh)
        return resp
    except Exception:
        return Response({"detail": "Invalid refresh"}, status=401)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    resp = Response({"ok": True})
    clear_auth_cookies(resp)
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({"user": UserSerializer(request.user).data})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def profile(request):
    ser = ProfileUpdateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    for f in ["first_name", "last_name"]:
        if f in ser.validated_data:
            setattr(request.user, f, ser.validated_data[f])
    request.user.save(update_fields=["first_name", "last_name"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_email(request):
    ser = ChangeEmailSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    phone = normalize_phone(request.user.phone)
    ok, reason = _verify_and_consume_code(phone, "change_email", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return Response({"detail": "Invalid or expired code"}, status=status_code)

    request.user.email = ser.validated_data.get("email") or None
    request.user.save(update_fields=["email"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_phone(request):
    ser = ChangePhoneSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    new_phone = ser.validated_data["new_phone"]
    ok, reason = _verify_and_consume_code(new_phone, "change_phone", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return Response({"detail": "Invalid or expired code"}, status=status_code)

    request.user.phone = new_phone
    request.user.save(update_fields=["phone"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    ser = ChangePasswordSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    phone = normalize_phone(request.user.phone)
    ok, reason = _verify_and_consume_code(phone, "change_password", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return Response({"detail": "Invalid or expired code"}, status=status_code)

    request.user.set_password(ser.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    resp = Response({"ok": True})
    clear_auth_cookies(resp)
    return resp

class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = None  # disable the default field validation

    def validate(self, attrs):
        request = self.context['request']
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if not refresh_token:
            raise serializers.ValidationError('No refresh token found in cookies.')
        attrs['refresh'] = refresh_token
        return super().validate(attrs)

class CookieTokenRefreshView(TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        # Set new cookies (access and possibly refresh)
        set_auth_cookies(
            response,
            serializer.validated_data['access'],
            serializer.validated_data.get('refresh', '')  # if rotation is on
        )
        return response