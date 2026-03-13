from rest_framework import serializers

from apps.accounts.models import GroupDiscount
from apps.catalog.models import Product, Service
from .models import DeliveryOption, Order


class DeliveryOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOption
        fields = ("id", "name", "description", "price_cents", "currency")


class OrderSerializer(serializers.ModelSerializer):
    delivery_option = DeliveryOptionSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "currency",
            "total_cents",
            "items",
            "email",
            "customer_name",
            "customer_address",
            "delivery_option",
            "created_at",
            "updated_at",
        )


class CreateCheckoutSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    currency = serializers.CharField(required=False)
    email = serializers.EmailField(required=True)
    customer_name = serializers.CharField(required=True, max_length=200)
    customer_address = serializers.CharField(required=True, max_length=500)
    delivery_option_id = serializers.IntegerField(required=True)

    def _resolve_discount(self):
        req = self.context.get("request")
        user = getattr(req, "user", None)
        if not user or not user.is_authenticated:
            return 0
        result = (
            GroupDiscount.objects.filter(group__user=user, is_active=True)
            .order_by("-percentage")
            .values_list("percentage", flat=True)
            .first()
        )
        return int(result or 0)

    def validate_delivery_option_id(self, value):
        try:
            return DeliveryOption.objects.get(id=value, is_active=True)
        except DeliveryOption.DoesNotExist as exc:
            raise serializers.ValidationError("Invalid delivery option") from exc

    def validate_items(self, items):
        normalized_items = []
        total = 0
        currency = None
        discount_pct = self._resolve_discount()

        product_ids = [int(it["product_id"]) for it in items if it.get("product_id")]
        service_ids = [int(it["service_id"]) for it in items if it.get("service_id")]

        products = Product.objects.filter(id__in=product_ids, is_active=True)
        services = Service.objects.filter(id__in=service_ids, is_active=True)
        product_map = {obj.id: obj for obj in products}
        service_map = {obj.id: obj for obj in services}

        for raw in items:
            qty = int(raw.get("qty", 1))
            if qty <= 0:
                raise serializers.ValidationError("Invalid item quantity")

            product_id = raw.get("product_id")
            service_id = raw.get("service_id")
            if bool(product_id) == bool(service_id):
                raise serializers.ValidationError("Each item must contain exactly one of product_id or service_id")

            if product_id:
                obj = product_map.get(int(product_id))
                if not obj:
                    raise serializers.ValidationError("Invalid product")
                name = obj.name
                base_unit_price_cents = obj.price_cents
                item_currency = obj.currency
                item_type = "product"
                item_ref = {"product_id": obj.id}
            else:
                obj = service_map.get(int(service_id))
                if not obj:
                    raise serializers.ValidationError("Invalid service")
                name = obj.name
                base_unit_price_cents = obj.base_price_cents
                item_currency = obj.currency
                item_type = "service"
                item_ref = {"service_id": obj.id}

            discounted_unit_price_cents = base_unit_price_cents
            if discount_pct > 0:
                discounted_unit_price_cents = (base_unit_price_cents * (100 - discount_pct)) // 100

            normalized_items.append(
                {
                    "type": item_type,
                    **item_ref,
                    "name": name,
                    "qty": qty,
                    "base_unit_price_cents": base_unit_price_cents,
                    "unit_price_cents": discounted_unit_price_cents,
                    "discount_percent": discount_pct,
                }
            )

            if currency is None:
                currency = item_currency
            elif currency != item_currency:
                raise serializers.ValidationError("All items must use the same currency")

            total += qty * discounted_unit_price_cents

        self.context["items_total_cents"] = total
        self.context["currency"] = currency or "EUR"
        return normalized_items

    def validate(self, attrs):
        requested_currency = attrs.get("currency")
        resolved_currency = self.context.get("currency", "EUR")
        if requested_currency and requested_currency.upper() != resolved_currency.upper():
            raise serializers.ValidationError({"currency": "Currency mismatch with selected catalog items"})

        delivery_option = attrs["delivery_option_id"]
        if delivery_option.currency.upper() != resolved_currency.upper():
            raise serializers.ValidationError({"delivery_option_id": "Delivery currency does not match cart currency"})

        attrs["currency"] = resolved_currency
        attrs["delivery_option"] = delivery_option
        attrs["total_cents"] = self.context.get("items_total_cents", 0) + delivery_option.price_cents
        return attrs


class CreateOrderSerializer(CreateCheckoutSerializer):
    pass
