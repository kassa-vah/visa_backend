"""
Paystack API client — verification only. The frontend's inline popup
already collects the payment; this module exists so the backend NEVER
trusts a client-reported "it succeeded" and instead re-checks with
Paystack directly, plus validates webhook signatures for the async path.

Usage:
    from services.payments.paystack import verify_transaction, is_valid_webhook_signature

    data = verify_transaction(reference)
    if data["status"] == "success":
        ... mark_success(...)
"""

import hashlib
import hmac

import requests
from django.conf import settings

BASE_URL = "https://api.paystack.co"


class PaystackError(Exception):
    """Raised when Paystack verification fails or returns an error status."""


def _headers():
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}


def verify_transaction(reference: str) -> dict:
    """
    Calls GET /transaction/verify/:reference. This is the only source of
    truth for whether a Paystack payment actually succeeded — the
    `callback` the frontend receives from PaystackPop is not sufficient
    on its own, since it's reported by the client's browser.

    Returns the `data` object from Paystack's response, e.g.:
        {
            "status": "success",
            "reference": "...",
            "amount": 50000,          # kobo/cents — divide by 100 for KES
            "currency": "KES",
            "customer": {"email": "..."},
            "metadata": {...},
            ...
        }
    Raises PaystackError if the HTTP call fails or Paystack reports
    `status: false` (i.e. the API call itself, not the transaction, failed).
    """
    resp = requests.get(
        f"{BASE_URL}/transaction/verify/{reference}",
        headers=_headers(),
        timeout=15,
    )
    body = resp.json() if resp.content else {}

    if not resp.ok or not body.get("status"):
        raise PaystackError(body.get("message") or f"Paystack verification failed: {resp.status_code}")

    return body["data"]


def is_valid_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Paystack signs webhook payloads with HMAC-SHA512 of the raw request
    body, using your secret key. Compare against the `x-paystack-signature`
    header before trusting anything in a webhook POST.
    """
    if not signature_header:
        return False
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed, signature_header)


def kobo_to_kes(amount_in_kobo) -> float:
    """Paystack amounts are in the smallest currency unit (cents/kobo)."""
    return round(float(amount_in_kobo) / 100, 2)