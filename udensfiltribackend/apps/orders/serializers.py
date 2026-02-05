from rest_framework import serializers
from .models import Order

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model=Order
        fields=("id","status","currency","total_cents","items","created_at","updated_at")

class CreateCheckoutSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    currency = serializers.CharField(required=False, default="EUR")
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    def validate_items(self, items):
        total = 0
        norm = []
        for it in items:
            name = str(it.get("name","")).strip()
            qty = int(it.get("qty", 1))
            unit = int(it.get("unit_price_cents", 0))
            if not name or qty <= 0 or unit < 0:
                raise serializers.ValidationError("Invalid item")
            total += qty * unit
            norm.append({"name": name, "qty": qty, "unit_price_cents": unit})
        self.context["total_cents"] = total
        return norm
