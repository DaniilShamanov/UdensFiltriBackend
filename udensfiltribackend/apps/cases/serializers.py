from rest_framework import serializers
from .models import Equipment, PlumbingCase, CaseMessage

class EquipmentSerializer(serializers.ModelSerializer):
    class Meta: model=Equipment; fields=("id","name","manufacturer","model","serial_number","notes")

class CaseMessageSerializer(serializers.ModelSerializer):
    sender_phone = serializers.CharField(source="sender.phone", read_only=True)
    class Meta:
        model=CaseMessage
        fields=("id","case","sender","sender_phone","message","is_internal","created_at")
        read_only_fields=("sender","created_at")
    def validate_is_internal(self, value):
        req = self.context.get("request")
        if value and (not req.user.is_superuser):
            raise serializers.ValidationError("Only superuser can create internal notes")
        return value

    def validate_case(self, value):
        req = self.context.get("request")
        if req and req.user.is_authenticated and (not req.user.is_superuser) and value.user_id != req.user.id:
            raise serializers.ValidationError("You cannot post messages to this case")
        return value

class PlumbingCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model=PlumbingCase
        fields=("id","title","description","status","priority","equipment","created_at","updated_at")
        read_only_fields=("status","created_at","updated_at")

class PlumbingCaseDetailSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()
    equipment_detail = EquipmentSerializer(source="equipment", read_only=True)
    class Meta:
        model=PlumbingCase
        fields=("id","title","description","status","priority","equipment","equipment_detail","created_at","updated_at","messages")
    def get_messages(self, obj):
        qs = obj.messages.all()
        req = self.context.get("request")
        if req and not req.user.is_superuser:
            qs = qs.filter(is_internal=False)
        return CaseMessageSerializer(qs, many=True).data
