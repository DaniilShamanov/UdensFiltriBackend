import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import User


SQLI_PATTERN = re.compile(r"(--|/\*|\*/|;|\b(select|union|insert|update|delete|drop|alter|truncate|exec|xp_)\b)", re.IGNORECASE)


def _contains_sqli_payload(value: str) -> bool:
    return bool(SQLI_PATTERN.search((value or "").strip()))


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "email", "first_name", "last_name")


class RequestEmailCodeSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=["register", "change_email", "change_password"])
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        req = self.context["request"]
        purpose = attrs["purpose"]
        email = (attrs.get("email") or "").strip().lower()

        if purpose == "register":
            if not email:
                raise serializers.ValidationError({"email": serializers.ErrorDetail(_("Email is required."), code="required")})
            attrs["email"] = email
            return attrs

        if not req.user.is_authenticated:
            raise serializers.ValidationError(serializers.ErrorDetail(_("Authentication required."), code="authentication_required"))
        if not req.user.email:
            raise serializers.ValidationError({"email": serializers.ErrorDetail(_("Current user email is not set."), code="missing_email")})

        attrs["email"] = req.user.email.lower()
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={"min_length": _("Password must be at least 6 characters long.")},
    )
    code = serializers.CharField(min_length=6, max_length=6)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if _contains_sqli_payload(email):
            raise serializers.ValidationError(serializers.ErrorDetail(_("Invalid email."), code="invalid_email"))
        return email


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if _contains_sqli_payload(email):
            raise serializers.ValidationError(serializers.ErrorDetail(_("Invalid email."), code="invalid_email"))
        return email

    def validate(self, attrs):
        email = attrs["email"]
        password = attrs["password"]

        if _contains_sqli_payload(password):
            raise serializers.ValidationError(serializers.ErrorDetail(_("Invalid credentials."), code="invalid_credentials"))

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError(serializers.ErrorDetail(_("Invalid credentials."), code="invalid_credentials"))

        attrs["user"] = user
        return attrs


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)


class ChangePhoneSerializer(serializers.Serializer):
    new_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)

    def validate_new_phone(self, value):
        if value is None:
            return None
        phone = value.strip()
        return phone or None


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={"min_length": _("Password must be at least 6 characters long.")},
    )
    code = serializers.CharField(min_length=6, max_length=6)
