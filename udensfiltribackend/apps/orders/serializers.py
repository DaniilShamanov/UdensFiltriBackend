from rest_framework import serializers
from apps.accounts.models import GroupDiscount
from apps.catalog.models import Product   # Service import removed
from .models import DeliveryOption, Order


class DeliveryOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOption
        fields = ("id", "name", "description", "price_cents")


class OrderItemSerializer(serializers.Serializer):
    """Transform stored item dict for API output – products only."""
    product_id = serializers.IntegerField()  # required, no longer optional
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.SerializerMethodField()

    def get_unit_price(self, obj):
        return obj.get('price_cents', 0) / 100

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('price_cents', None)
        # type is always 'product' now, so you can add it or omit
        data['type'] = 'product'
        return data


class OrderSerializer(serializers.ModelSerializer):
    delivery_option = DeliveryOptionSerializer(read_only=True)
    items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "total_price",
            "items",
            "email",
            "customer_name",
            "customer_address",
            "delivery_option",
            "created_at",
            "updated_at",
        )

    def get_items(self, obj):
        raw_items = obj.items or []
        product_items = []
        for item in raw_items:
            if item.get('product_id') and item.get('name') is not None and item.get('quantity'):
                if 'price_cents' not in item:
                    item['price_cents'] = 0
                product_items.append(item)
        return OrderItemSerializer(product_items, many=True).data

    def get_total_price(self, obj):
        return obj.total_cents / 100


class CreateCheckoutSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    customer_name = serializers.CharField(required=True, max_length=200)
    customer_address = serializers.CharField(required=True, max_length=500)
    delivery_option_id = serializers.IntegerField(required=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def _resolve_discount(self):
        req = self.context.get("request")
        user = getattr(req, "user", None)
        if not user or not user.is_authenticated:
            return 0
        try:
            result = (
                GroupDiscount.objects.filter(group__user=user, is_active=True)
                .order_by("-percentage")
                .values_list("percentage", flat=True)
                .first()
            )
            return int(result or 0)
        except Exception:
            return 0

    def validate_delivery_option_id(self, value):
        try:
            return DeliveryOption.objects.get(id=value, is_active=True)
        except DeliveryOption.DoesNotExist:
            raise serializers.ValidationError("Invalid delivery option")

    def validate_items(self, items):
        normalized_items = []
        total_cents = 0
        discount_percent = self._resolve_discount()

        product_ids = []
        for raw in items:
            pid = raw.get("product_id")
            if not pid:
                raise serializers.ValidationError("Each item must have product_id")
            product_ids.append(int(pid))

        products = Product.objects.filter(id__in=product_ids, is_active=True)
        product_map = {obj.id: obj for obj in products}

        for raw in items:
            quantity = raw.get("quantity")
            if not quantity or quantity <= 0:
                raise serializers.ValidationError("Quantity must be a positive integer")

            product_id = int(raw["product_id"])
            obj = product_map.get(product_id)
            if not obj:
                raise serializers.ValidationError(f"Invalid product ID {product_id}")

            final_price_cents = obj.price_cents
            if discount_percent > 0:
                final_price_cents = (obj.price_cents * (100 - discount_percent)) // 100

            normalized_items.append({
                "product_id": obj.id,
                "name": obj.name,
                "quantity": quantity,
                "price_cents": final_price_cents,
                "type": "product",
            })

            total_cents += quantity * final_price_cents

        self.context["items_total_cents"] = total_cents
        return normalized_items

    def validate(self, attrs):
        delivery_option = attrs["delivery_option_id"]
        attrs["delivery_option"] = delivery_option
        attrs["total_cents"] = self.context.get("items_total_cents", 0) + delivery_option.price_cents
        return attrs