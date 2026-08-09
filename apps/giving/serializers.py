from decimal import Decimal

from rest_framework import serializers

from .models import Donation, Offering, PaymentMethod, PaymentStatus

MIN_AMOUNT = Decimal("1")


# ── Read serializers ─────────────────────────────────────────────────────

class OfferingReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offering
        fields = [
            "id", "giving_type", "amount", "donor_name", "note",
            "payment_method", "status", "mpesa_receipt_number",
            "paystack_reference", "created_at",
        ]
        read_only_fields = fields


class DonationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donation
        fields = [
            "id", "campaign", "amount", "donor_name", "note",
            "payment_method", "status", "mpesa_receipt_number",
            "paystack_reference", "created_at",
        ]
        read_only_fields = fields


# ── M-Pesa: POST /offerings (and /donations) ────────────────────────────
# Mirrors the body Offerings.jsx sends for method === "mpesa":
#   { amount, payment_method: "mpesa", giving_type, donor_name, phone_number, note }

class OfferingMpesaCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=MIN_AMOUNT)
    payment_method = serializers.ChoiceField(choices=[PaymentMethod.MPESA])
    giving_type = serializers.ChoiceField(choices=Offering._meta.get_field("giving_type").choices)
    donor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="Anonymous")
    phone_number = serializers.CharField(max_length=15)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_phone_number(self, value):
        cleaned = value.replace(" ", "")
        import re
        if not re.match(r"^(\+?254|0)[17]\d{8}$", cleaned):
            raise serializers.ValidationError("Enter a valid Kenyan number, e.g. 07XX XXX XXX.")
        return cleaned


class DonationMpesaCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=MIN_AMOUNT)
    payment_method = serializers.ChoiceField(choices=[PaymentMethod.MPESA])
    campaign = serializers.CharField(max_length=150, required=False, allow_blank=True, default="general")
    donor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="Anonymous")
    phone_number = serializers.CharField(max_length=15)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_phone_number(self, value):
        cleaned = value.replace(" ", "")
        import re
        if not re.match(r"^(\+?254|0)[17]\d{8}$", cleaned):
            raise serializers.ValidationError("Enter a valid Kenyan number, e.g. 07XX XXX XXX.")
        return cleaned


# ── Paystack: POST /offerings/verify (and /donations/verify) ────────────
# Mirrors verifyPaystackOffering()'s body:
#   { reference, amount, giving_type, donor_name, donor_email, note }

class OfferingPaystackVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=MIN_AMOUNT)
    giving_type = serializers.ChoiceField(choices=Offering._meta.get_field("giving_type").choices)
    donor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="Anonymous")
    donor_email = serializers.EmailField()
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class DonationPaystackVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=MIN_AMOUNT)
    campaign = serializers.CharField(max_length=150, required=False, allow_blank=True, default="general")
    donor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="Anonymous")
    donor_email = serializers.EmailField()
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)