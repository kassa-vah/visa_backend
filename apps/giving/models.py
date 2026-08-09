import uuid

from django.core.validators import MinValueValidator
from django.db import models


class PaymentMethod(models.TextChoices):
    MPESA = "mpesa", "M-Pesa"
    PAYSTACK = "paystack", "Paystack"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class Contribution(models.Model):
    """
    Abstract base shared by Offering and Donation. Holds everything that is
    identical between the two: who gave, how much, how they paid, and the
    provider-side bookkeeping needed to reconcile M-Pesa / Paystack payments.

    Nothing about *why* the money was given lives here — that's the job of
    the concrete subclasses (giving_type on Offering, purpose on Donation).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(1)],
        help_text="Amount in KES.",
    )
    donor_name = models.CharField(max_length=150, blank=True, default="Anonymous")
    note = models.TextField(blank=True, null=True)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )

    # M-Pesa (Daraja) bookkeeping
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    mpesa_checkout_request_id = models.CharField(
        max_length=100, blank=True, null=True, db_index=True,
        help_text="CheckoutRequestID returned by the STK push, used to match the callback.",
    )
    mpesa_merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)

    # Paystack bookkeeping
    donor_email = models.EmailField(blank=True, null=True)
    paystack_reference = models.CharField(
        max_length=100, blank=True, null=True, db_index=True
    )

    # Raw provider payloads kept for auditing / debugging reconciliation issues.
    provider_response = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def mark_success(self, *, receipt=None, provider_response=None):
        self.status = PaymentStatus.SUCCESS
        if receipt and self.payment_method == PaymentMethod.MPESA:
            self.mpesa_receipt_number = receipt
        if provider_response is not None:
            self.provider_response = provider_response
        self.save(update_fields=["status", "mpesa_receipt_number", "provider_response", "updated_at"])

    def mark_failed(self, *, provider_response=None):
        self.status = PaymentStatus.FAILED
        if provider_response is not None:
            self.provider_response = provider_response
        self.save(update_fields=["status", "provider_response", "updated_at"])


class GivingType(models.TextChoices):
    TITHE = "tithe", "Tithe"
    OFFERING = "offering", "Offering"
    THANKSGIVING = "thanksgiving", "Thanksgiving"
    OTHER = "other", "Other"


class Offering(Contribution):
    """
    Regular church giving: tithe, offering, thanksgiving, or an
    unclassified 'other' gift. Matches the Offerings.jsx form 1:1 —
    giving_type is the only field that distinguishes this from Donation.
    """

    giving_type = models.CharField(max_length=20, choices=GivingType.choices)

    class Meta(Contribution.Meta):
        verbose_name = "Offering"
        verbose_name_plural = "Offerings"

    def __str__(self):
        return f"{self.get_giving_type_display()} · KES {self.amount} · {self.donor_name or 'Anonymous'}"


class Donation(Contribution):
    """
    Open-ended giving toward a specific cause rather than a routine giving
    type — building fund, missions trip, benevolence, a fundraiser, etc.
    `campaign` is free text/slug rather than a fixed choice set because
    campaigns come and go and shouldn't require a migration each time.
    """

    campaign = models.CharField(
        max_length=150, blank=True, default="general",
        help_text="What the donation is earmarked for, e.g. 'building-fund', 'missions-2026'.",
    )

    class Meta(Contribution.Meta):
        verbose_name = "Donation"
        verbose_name_plural = "Donations"

    def __str__(self):
        return f"Donation · {self.campaign} · KES {self.amount} · {self.donor_name or 'Anonymous'}"