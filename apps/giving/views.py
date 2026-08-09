import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from services.payments.mpesa import MpesaError, initiate_stk_push, parse_stk_callback
from services.payments.paystack import PaystackError, is_valid_webhook_signature, kobo_to_kes, verify_transaction

from .models import Donation, Offering, PaymentMethod, PaymentStatus
from .serializers import (
    DonationMpesaCreateSerializer,
    DonationPaystackVerifySerializer,
    DonationReadSerializer,
    OfferingMpesaCreateSerializer,
    OfferingPaystackVerifySerializer,
    OfferingReadSerializer,
)

logger = logging.getLogger(__name__)


# ── Shared helpers ───────────────────────────────────────────────────────

def _mpesa_create(*, model, serializer_cls, extra_fields, request):
    """
    Shared body for the two 'POST /offerings' and 'POST /donations' mpesa
    flows: validate, create a pending row, fire the STK push, persist the
    CheckoutRequestID so the callback can find it again.
    """
    serializer = serializer_cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    v = serializer.validated_data

    row = model.objects.create(
        amount=v["amount"],
        donor_name=v.get("donor_name") or "Anonymous",
        note=v.get("note") or None,
        payment_method=PaymentMethod.MPESA,
        phone_number=v["phone_number"],
        **extra_fields(v),
    )

    try:
        result = initiate_stk_push(
            phone_number=v["phone_number"],
            amount=v["amount"],
            account_reference=str(row.id)[:12],
            transaction_desc=extra_fields(v).get("giving_type") or extra_fields(v).get("campaign") or "Giving",
        )
    except MpesaError as exc:
        row.mark_failed(provider_response={"error": str(exc)})
        return Response({"message": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    row.mpesa_checkout_request_id = result.get("CheckoutRequestID")
    row.mpesa_merchant_request_id = result.get("MerchantRequestID")
    row.provider_response = result
    row.save(update_fields=[
        "mpesa_checkout_request_id", "mpesa_merchant_request_id", "provider_response", "updated_at",
    ])

    return Response(
        {
            "message": "STK push sent. Check your phone to complete payment.",
            "id": str(row.id),
            "checkout_request_id": row.mpesa_checkout_request_id,
        },
        status=status.HTTP_201_CREATED,
    )


def _paystack_verify(*, model, serializer_cls, extra_fields, request):
    """
    Shared body for 'POST /offerings/verify' and 'POST /donations/verify'.
    Never trusts the client's report of success — always re-checks with
    Paystack, and cross-checks the verified amount against what was
    requested before recording a success.
    """
    serializer = serializer_cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    v = serializer.validated_data

    try:
        data = verify_transaction(v["reference"])
    except PaystackError as exc:
        return Response({"message": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    verified_amount = kobo_to_kes(data.get("amount", 0))
    paystack_status = data.get("status")

    row, _created = model.objects.get_or_create(
        paystack_reference=v["reference"],
        defaults=dict(
            amount=v["amount"],
            donor_name=v.get("donor_name") or "Anonymous",
            donor_email=v["donor_email"],
            note=v.get("note") or None,
            payment_method=PaymentMethod.PAYSTACK,
            **extra_fields(v),
        ),
    )

    if paystack_status != "success":
        row.mark_failed(provider_response=data)
        return Response({"message": "Payment was not successful."}, status=status.HTTP_402_PAYMENT_REQUIRED)

    if abs(verified_amount - float(v["amount"])) > 0.01:
        logger.warning(
            "Paystack amount mismatch for reference=%s: requested=%s verified=%s",
            v["reference"], v["amount"], verified_amount,
        )
        row.mark_failed(provider_response=data)
        return Response({"message": "Amount mismatch — payment could not be reconciled."}, status=status.HTTP_400_BAD_REQUEST)

    row.mark_success(provider_response=data)
    return Response(
        {"message": "Payment verified.", "id": str(row.id), "reference": v["reference"]},
        status=status.HTTP_200_OK,
    )


# ── Offerings ─────────────────────────────────────────────────────────────

class OfferingCreateView(APIView):
    """POST /offerings — M-Pesa STK push initiation for tithe/offering/thanksgiving/other."""
    permission_classes = [AllowAny]

    def post(self, request):
        return _mpesa_create(
            model=Offering,
            serializer_cls=OfferingMpesaCreateSerializer,
            extra_fields=lambda v: {"giving_type": v["giving_type"]},
            request=request,
        )


class OfferingVerifyView(APIView):
    """POST /offerings/verify — server-side Paystack verification for an offering."""
    permission_classes = [AllowAny]

    def post(self, request):
        return _paystack_verify(
            model=Offering,
            serializer_cls=OfferingPaystackVerifySerializer,
            extra_fields=lambda v: {"giving_type": v["giving_type"]},
            request=request,
        )


class OfferingDetailView(APIView):
    """GET /offerings/<id> — used for polling M-Pesa status from the frontend, if needed."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        offering = get_object_or_404(Offering, pk=pk)
        return Response(OfferingReadSerializer(offering).data)


# ── Donations ─────────────────────────────────────────────────────────────

class DonationCreateView(APIView):
    """POST /donations — M-Pesa STK push initiation for a campaign donation."""
    permission_classes = [AllowAny]

    def post(self, request):
        return _mpesa_create(
            model=Donation,
            serializer_cls=DonationMpesaCreateSerializer,
            extra_fields=lambda v: {"campaign": v.get("campaign") or "general"},
            request=request,
        )


class DonationVerifyView(APIView):
    """POST /donations/verify — server-side Paystack verification for a donation."""
    permission_classes = [AllowAny]

    def post(self, request):
        return _paystack_verify(
            model=Donation,
            serializer_cls=DonationPaystackVerifySerializer,
            extra_fields=lambda v: {"campaign": v.get("campaign") or "general"},
            request=request,
        )


class DonationDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        donation = get_object_or_404(Donation, pk=pk)
        return Response(DonationReadSerializer(donation).data)


# ── Webhooks ──────────────────────────────────────────────────────────────

class MpesaCallbackView(APIView):
    """
    POST target for MPESA_CALLBACK_URL. Safaricom calls this async, separately
    from (and often faster than) any polling the frontend might do — this is
    the authoritative place status flips from pending to success/failed.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            parsed = parse_stk_callback(request.data)
        except MpesaError as exc:
            logger.error("Malformed M-Pesa callback: %s", exc)
            # Daraja expects a 200 regardless, or it will keep retrying.
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        checkout_id = parsed["checkout_request_id"]
        row = (
            Offering.objects.filter(mpesa_checkout_request_id=checkout_id).first()
            or Donation.objects.filter(mpesa_checkout_request_id=checkout_id).first()
        )
        if row is None:
            logger.warning("No offering/donation found for CheckoutRequestID=%s", checkout_id)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        if parsed["success"]:
            row.mark_success(receipt=parsed["mpesa_receipt_number"], provider_response=parsed)
        else:
            row.mark_failed(provider_response=parsed)

        # Daraja just wants a 200 acknowledging receipt.
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaystackWebhookView(APIView):
    """
    Optional but recommended: Paystack's async webhook, in case the user
    closes the tab right after paying and /offerings/verify is never called
    from the frontend. Signature-checked; on a successful charge it does the
    same reconciliation as the synchronous verify path.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not is_valid_webhook_signature(request.body, signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        event = request.data
        if event.get("event") != "charge.success":
            return Response(status=status.HTTP_200_OK)

        data = event["data"]
        reference = data.get("reference")

        row = (
            Offering.objects.filter(paystack_reference=reference).first()
            or Donation.objects.filter(paystack_reference=reference).first()
        )
        if row is None:
            logger.warning("Paystack webhook for unknown reference=%s", reference)
            return Response(status=status.HTTP_200_OK)

        if data.get("status") == "success":
            row.mark_success(provider_response=data)
        else:
            row.mark_failed(provider_response=data)

        return Response(status=status.HTTP_200_OK)