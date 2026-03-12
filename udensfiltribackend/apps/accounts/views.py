from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import clear_auth_cookies, set_auth_cookies
from .models import EmailCode, User
from .serializers import (
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    ChangePhoneSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    RequestEmailCodeSerializer,
    UserSerializer,
)
from .throttles import CodeEmailThrottle, CodeIPThrottle
from .utils import create_email_code


def _error_response(code: str, message: str, status_code: int, fields=None):
    payload = {"error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    return Response(payload, status=status_code)


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_cookie(request):
    token = get_token(request)
    return JsonResponse({"csrfToken": token})


def _issue_tokens(user: User):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _get_latest_active_code(email: str, purpose: str) -> Optional[EmailCode]:
    return (
        EmailCode.objects.filter(email=email, purpose=purpose, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )


def _verify_and_consume_code(email: str, purpose: str, code: str):
    obj = _get_latest_active_code(email, purpose)
    if not obj:
        return False, "missing"
    if timezone.now() >= obj.expires_at:
        return False, "expired"
    if obj.is_locked:
        return False, "locked"
    if obj.code != code:
        obj.failed_attempts += 1
        if obj.failed_attempts >= 5:
            obj.locked_until = timezone.now() + timedelta(minutes=15)
        obj.save(update_fields=["failed_attempts", "locked_until"])
        return False, "invalid"
    obj.consume()
    return True, "ok"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([CodeIPThrottle, CodeEmailThrottle])
def request_email_code(request):
    ser = RequestEmailCodeSerializer(data=request.data, context={"request": request})
    ser.is_valid(raise_exception=True)
    email = ser.validated_data["email"]
    purpose = ser.validated_data["purpose"]
    try:
        code_obj = create_email_code(email, purpose)
    except ValueError as exc:
        return _error_response("code_rate_limited", str(exc), 429)
    if getattr(settings, "EMAIL_CODE_MOCK_MODE", False):
        return Response({"ok": True, "mock_code": code_obj.code})
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    email = ser.validated_data["email"].lower()
    ok, reason = _verify_and_consume_code(email, "register", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return _error_response("invalid_code", _("Invalid or expired code."), status_code)

    if User.objects.filter(email__iexact=email).exists():
        return _error_response("email_exists", _("User with this email already exists."), 400)

    user = User.objects.create_user(
        password=ser.validated_data["password"],
        email=email,
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
    refresh_cookie = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
    if not refresh_cookie:
        return _error_response("missing_refresh_cookie", _("No refresh cookie."), 401)
    try:
        token = RefreshToken(refresh_cookie)
        new_access = str(token.access_token)
        new_refresh = str(token)
        resp = Response({"ok": True})
        set_auth_cookies(resp, new_access, new_refresh)
        return resp
    except TokenError:
        return _error_response("invalid_refresh", _("Invalid refresh token."), 401)


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
    update_fields = []
    for field in ["first_name", "last_name"]:
        if field in ser.validated_data:
            setattr(request.user, field, ser.validated_data[field])
            update_fields.append(field)
    if update_fields:
        request.user.save(update_fields=update_fields)
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_email(request):
    ser = ChangeEmailSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    if not request.user.email:
        return _error_response("missing_email", _("User email is not set."), 400)

    ok, reason = _verify_and_consume_code(request.user.email.lower(), "change_email", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return _error_response("invalid_code", _("Invalid or expired code."), status_code)

    new_email = ser.validated_data["new_email"].strip().lower()
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return _error_response("email_exists", _("User with this email already exists."), 400)

    request.user.email = new_email
    request.user.save(update_fields=["email"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_phone(request):
    ser = ChangePhoneSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    new_phone = ser.validated_data.get("new_phone")
    if new_phone and User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
        return _error_response("phone_exists", _("User with this phone already exists."), 400)

    request.user.phone = new_phone
    request.user.save(update_fields=["phone"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    ser = ChangePasswordSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    if not request.user.email:
        return _error_response("missing_email", _("User email is not set."), 400)

    ok, reason = _verify_and_consume_code(request.user.email.lower(), "change_password", ser.validated_data["code"])
    if not ok:
        status_code = 429 if reason == "locked" else 400
        return _error_response("invalid_code", _("Invalid or expired code."), status_code)

    request.user.set_password(ser.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    resp = Response({"ok": True})
    clear_auth_cookies(resp)
    return resp
