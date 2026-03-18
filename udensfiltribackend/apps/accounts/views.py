from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
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
    UserSerializer,
)
from .utils import create_email_code, send_verification_email

def _error_response(code, message, status_code, fields=None):
    payload = {"error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    return Response(payload, status=status_code)


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _verify_and_consume_code(email, purpose, code):
    """Returns (success, reason) where reason is 'ok' or error key."""
    try:
        obj = EmailCode.objects.filter(
            email=email,
            purpose=purpose,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now()
        ).latest('created_at')
    except EmailCode.DoesNotExist:
        return False, "missing"

    if obj.is_locked:
        return False, "locked"

    if obj.code != code:
        obj.failed_attempts += 1
        if obj.failed_attempts >= 5:
            obj.locked_until = timezone.now() + timedelta(minutes=15)
        obj.save(update_fields=['failed_attempts', 'locked_until'])
        return False, "invalid"

    obj.consume()
    return True, "ok"


# ---------- Public endpoints ----------
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_cookie(request):
    return JsonResponse({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def send_code(request):
    email = request.data.get('email')
    purpose = request.data.get('purpose')
    if not email or not purpose:
        return _error_response("missing_fields", _("Email and purpose are required."), 400)

    # Optionally, check if email already exists for register purpose
    if purpose == "register" and User.objects.filter(email__iexact=email).exists():
        return _error_response("email_exists", _("Email already registered."), 400)

    try:
        code_record = create_email_code(email=email, purpose=purpose, ttl_minutes=10)
    except ValueError:
        min_interval = getattr(settings, "EMAIL_CODE_MIN_INTERVAL_SECONDS", 60)
        last_code = EmailCode.objects.filter(email=email, purpose=purpose).order_by("-created_at").first()
        elapsed = (timezone.now() - last_code.created_at).total_seconds() if last_code else 0
        wait = max(int(min_interval - elapsed), 1)
        return _error_response(
            "too_many_requests",
            _(f"Please wait {wait} seconds before requesting a new code."),
            429,
        )

    send_verification_email(email, code_record.code, purpose)

    return Response({"message": _("Verification code sent.")})


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    email = ser.validated_data["email"].lower()
    code = ser.validated_data["code"]

    ok, reason = _verify_and_consume_code(email, "register", code)
    if not ok:
        status_map = {"missing": 400, "expired": 400, "invalid": 400, "locked": 429}
        return _error_response("invalid_code", _("Invalid or expired code."), status_map.get(reason, 400))

    if User.objects.filter(email__iexact=email).exists():
        return _error_response("email_exists", _("Email already registered."), 400)

    user = User.objects.create_user(
        password=ser.validated_data["password"],
        email=email,
        first_name=ser.validated_data.get("first_name", ""),
        last_name=ser.validated_data.get("last_name", ""),
    )
    # User is active immediately – no separate activation step.
    user.is_active = True
    user.save(update_fields=["is_active"])

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
@permission_classes([AllowAny])
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

    # The code should have been sent to the current email (or new? Usually current)
    current_email = request.user.email
    if not current_email:
        return _error_response("missing_email", _("User email is not set."), 400)

    ok, reason = _verify_and_consume_code(current_email, "change_email", ser.validated_data["code"])
    if not ok:
        status_map = {"missing": 400, "expired": 400, "invalid": 400, "locked": 429}
        return _error_response("invalid_code", _("Invalid or expired code."), status_map.get(reason, 400))

    new_email = ser.validated_data["new_email"].strip().lower()
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return _error_response("email_exists", _("Email already in use."), 400)

    request.user.email = new_email
    request.user.save(update_fields=["email"])
    return Response({"user": UserSerializer(request.user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    ser = ChangePasswordSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    current_email = request.user.email
    if not current_email:
        return _error_response("missing_email", _("User email is not set."), 400)

    ok, reason = _verify_and_consume_code(current_email, "change_password", ser.validated_data["code"])
    if not ok:
        status_map = {"missing": 400, "expired": 400, "invalid": 400, "locked": 429}
        return _error_response("invalid_code", _("Invalid or expired code."), status_map.get(reason, 400))

    request.user.set_password(ser.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    # Invalidate tokens by clearing cookies
    resp = Response({"ok": True})
    clear_auth_cookies(resp)
    return resp


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    email = request.data.get('email')
    code = request.data.get('code')
    new_password = request.data.get('new_password')

    if not email or not code or not new_password:
        return Response({'error': 'email, code and new_password are required'}, status=400)

    # Find the most recent valid code for this email with purpose 'reset_password'
    try:
        code_record = EmailCode.objects.filter(
            email=email,
            purpose='reset_password',
            consumed_at__isnull=True,
            expires_at__gt=timezone.now()
        ).latest('created_at')
    except EmailCode.DoesNotExist:
        return Response({'error': 'No valid code found. Request a new one.'}, status=400)

    if code_record.is_locked:
        return Response({'error': 'Too many attempts. Try again later.'}, status=429)

    if code_record.code != code:
        code_record.failed_attempts += 1
        if code_record.failed_attempts >= 5:
            code_record.lock(seconds=300)
        code_record.save(update_fields=['failed_attempts', 'locked_until'])
        return Response({'error': 'Invalid code'}, status=400)

    # Code correct – mark as consumed
    code_record.consume()

    # Find the user by email
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Set new password
    user.set_password(new_password)
    user.save(update_fields=['password'])

    # Optionally, log the user out everywhere by rotating tokens or clearing sessions.
    # For simplicity, we just return success. The frontend should redirect to login.

    return Response({'message': 'Password reset successfully'})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_phone(request):
    ser = ChangePhoneSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    new_phone = ser.validated_data.get("new_phone")
    if new_phone and User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
        return _error_response("phone_exists", _("Phone already in use."), 400)

    request.user.phone = new_phone
    request.user.save(update_fields=["phone"])
    return Response({"user": UserSerializer(request.user).data})
