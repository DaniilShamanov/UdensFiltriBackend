from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager, Group
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from datetime import timedelta


REGULAR_USERS_GROUP = "regular_users"
BUSINESS_USERS_GROUP = "business_users"


class UserManager(BaseUserManager):
    def create_user(self, phone: str = "", password=None, **extra_fields):
        user = self.model(phone=(phone or "").strip() or None, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=Q(email__isnull=False),
                name="accounts_user_email_ci_unique",
            )
        ]

    phone = models.CharField(max_length=32, unique=True, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone or self.email or f"User #{self.pk}"


class GroupDiscount(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="discount")
    percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
        help_text="Discount percent to apply for users in this group",
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("group__name",)

    def __str__(self):
        return f"{self.group.name}: {self.percentage}%"


class EmailCode(models.Model):
    PURPOSE_CHOICES = [
        ("register", "register"),
        ("change_email", "change_email"),
        ("change_phone", "change_phone"),
        ("change_password", "change_password"),
    ]

    email = models.EmailField()
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES)
    code = models.CharField(max_length=6)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)

    # Security / anti-bruteforce controls
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "created_at"]),
            models.Index(fields=["email", "purpose", "code"]),
        ]

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_locked(self):
        return self.locked_until is not None and timezone.now() < self.locked_until

    def lock(self, seconds: int):
        self.locked_until = timezone.now() + timedelta(seconds=seconds)
        self.save(update_fields=["locked_until"])

    def consume(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])
