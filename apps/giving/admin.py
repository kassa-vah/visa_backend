from django.contrib import admin

from .models import Donation, Offering


class ContributionAdminMixin:
    list_display = (
        "id", "amount", "donor_name", "payment_method", "status", "created_at",
    )
    list_filter = ("payment_method", "status", "created_at")
    search_fields = (
        "donor_name", "donor_email", "phone_number",
        "mpesa_receipt_number", "mpesa_checkout_request_id", "paystack_reference",
    )
    readonly_fields = (
        "id", "created_at", "updated_at", "provider_response",
        "mpesa_checkout_request_id", "mpesa_merchant_request_id", "mpesa_receipt_number",
        "paystack_reference",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Offering)
class OfferingAdmin(ContributionAdminMixin, admin.ModelAdmin):
    list_display = ContributionAdminMixin.list_display + ("giving_type",)
    list_filter = ContributionAdminMixin.list_filter + ("giving_type",)


@admin.register(Donation)
class DonationAdmin(ContributionAdminMixin, admin.ModelAdmin):
    list_display = ContributionAdminMixin.list_display + ("campaign",)
    list_filter = ContributionAdminMixin.list_filter + ("campaign",)