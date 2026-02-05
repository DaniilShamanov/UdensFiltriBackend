from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
from .utils import normalize_phone

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id","phone","email","first_name","last_name","is_superuser")

class RequestSMSCodeSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=["register","change_email","change_phone","change_password"])
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        req = self.context["request"]
        purpose = attrs["purpose"]
        phone = (attrs.get("phone") or "").strip()
        if purpose == "register":
            if not phone:
                raise serializers.ValidationError({"phone":"Phone is required"})
            attrs["phone"] = normalize_phone(phone)
        elif purpose == "change_phone":
            if not req.user.is_authenticated:
                raise serializers.ValidationError("Authentication required")
            if not phone:
                raise serializers.ValidationError({"phone":"New phone is required"})
            attrs["phone"] = normalize_phone(phone)
        else:
            if not req.user.is_authenticated:
                raise serializers.ValidationError("Authentication required")
            attrs["phone"] = normalize_phone(req.user.phone)
        return attrs

class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    code = serializers.CharField(min_length=6, max_length=6)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        return normalize_phone(value)

class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_phone(self, value):
        return normalize_phone(value)

    def validate(self, attrs):
        user = authenticate(phone=attrs["phone"], password=attrs["password"])
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
    new_phone = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)
    def validate_new_phone(self, value):
        return normalize_phone(value)

class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=8)
    code = serializers.CharField(min_length=6, max_length=6)
