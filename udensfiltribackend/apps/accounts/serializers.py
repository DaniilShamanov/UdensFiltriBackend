from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User
from .utils import normalize_phone


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "email", "first_name", "last_name")


class RequestEmailCodeSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=["register", "change_email", "change_phone", "change_password"])
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        req = self.context["request"]
        purpose = attrs["purpose"]
        email = (attrs.get("email") or "").strip().lower()

        if purpose == "register":
            if not email:
                raise serializers.ValidationError({"email": "Email is required"})
            attrs["email"] = email
        elif purpose == "change_email":
            if not req.user.is_authenticated:
                raise serializers.ValidationError("Authentication required")
            if not email:
                raise serializers.ValidationError({"email": "New email is required"})
            attrs["email"] = email
        else:
            if not req.user.is_authenticated:
                raise serializers.ValidationError("Authentication required")
            if not req.user.email:
                raise serializers.ValidationError({"email": "Current user email is not set"})
            attrs["email"] = req.user.email.lower()

        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    code = serializers.CharField(min_length=6, max_length=6)
    phone = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        if not value:
            return None
        return normalize_phone(value)


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = (attrs.get("phone") or "").strip()
        email = (attrs.get("email") or "").strip().lower()

        if phone:
            phone = normalize_phone(phone)
            user = authenticate(phone=phone, password=attrs["password"])
        elif email:
            user = User.objects.filter(email__iexact=email).first()
            if not user or not user.check_password(attrs["password"]):
                user = None
        else:
            raise serializers.ValidationError("Either phone or email must be provided")

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        attrs["user"] = user
        return attrs


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class ChangeEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    code = serializers.CharField(min_length=6, max_length=6)


class ChangePhoneSerializer(serializers.Serializer):
    new_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    code = serializers.CharField(min_length=6, max_length=6)

    def validate_new_phone(self, value):
        if not value:
            return None
        return normalize_phone(value)


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    code = serializers.CharField(min_length=6, max_length=6)
