"""
Safaricom Daraja API client (STK Push / Lipa na M-Pesa Online).

Plain `requests` calls — no SDK. Two environments are supported via
MPESA_ENV: "sandbox" (default) and "production".

Usage:
    from services.payments.mpesa import initiate_stk_push, parse_stk_callback

    result = initiate_stk_push(
        phone_number="0712345678",
        amount=500,
        account_reference="OFR-<id>",
        transaction_desc="Tithe",
    )
    # result["CheckoutRequestID"] -> store this on the Offering/Donation row

Callback handling (in your webhook view):
    parsed = parse_stk_callback(request.data)
    if parsed["success"]:
        ... mark_success(receipt=parsed["mpesa_receipt_number"], ...)
    else:
        ... mark_failed(...)
"""

import base64
import datetime
import time

import requests
from django.conf import settings

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"

_token_cache = {"access_token": None, "expires_at": 0}


class MpesaError(Exception):
    """Raised for any Daraja request that fails or returns a non-zero ResultCode."""


def _base_url():
    env = getattr(settings, "MPESA_ENV", "sandbox")
    return PRODUCTION_BASE_URL if env == "production" else SANDBOX_BASE_URL


def _get_access_token():
    """OAuth token, cached in-process until ~60s before expiry."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=15,
    )
    if not resp.ok:
        raise MpesaError(f"Failed to obtain M-Pesa access token: {resp.status_code} {resp.text}")

    data = resp.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3599))

    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in - 60
    return token


def _normalize_phone(phone_number: str) -> str:
    """Daraja wants 2547XXXXXXXX / 2541XXXXXXXX (no '+', no leading 0)."""
    cleaned = phone_number.replace(" ", "").replace("+", "")
    if cleaned.startswith("0"):
        cleaned = "254" + cleaned[1:]
    if not cleaned.startswith("254"):
        raise MpesaError(f"Unrecognized phone number format: {phone_number}")
    return cleaned


def _password_and_timestamp():
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def initiate_stk_push(*, phone_number: str, amount, account_reference: str, transaction_desc: str) -> dict:
    """
    Triggers the STK push (the prompt the user sees on their phone).
    Returns the raw Daraja JSON response on success; raises MpesaError otherwise.
    The caller should persist `CheckoutRequestID` to match the later callback.
    """
    token = _get_access_token()
    password, timestamp = _password_and_timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(round(float(amount))),
        "PartyA": _normalize_phone(phone_number),
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": _normalize_phone(phone_number),
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference[:12],  # Daraja truncates/rejects longer values
        "TransactionDesc": transaction_desc[:13],
    }

    resp = requests.post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    data = resp.json() if resp.content else {}

    if not resp.ok or data.get("ResponseCode") not in (0, "0"):
        raise MpesaError(data.get("errorMessage") or data.get("ResponseDescription") or str(data))

    return data


def parse_stk_callback(body: dict) -> dict:
    """
    Normalizes the nested Safaricom callback shape into something flat and
    easy to act on. `body` is the parsed JSON POSTed to your callback URL.

    Returns:
        {
            "checkout_request_id": str,
            "merchant_request_id": str,
            "success": bool,
            "result_code": int,
            "result_desc": str,
            "amount": float | None,
            "mpesa_receipt_number": str | None,
            "phone_number": str | None,
            "transaction_date": str | None,
        }
    """
    try:
        stk_callback = body["Body"]["stkCallback"]
    except (KeyError, TypeError) as exc:
        raise MpesaError(f"Unrecognized callback payload shape: {body}") from exc

    result_code = stk_callback.get("ResultCode")
    parsed = {
        "checkout_request_id": stk_callback.get("CheckoutRequestID"),
        "merchant_request_id": stk_callback.get("MerchantRequestID"),
        "success": result_code == 0,
        "result_code": result_code,
        "result_desc": stk_callback.get("ResultDesc"),
        "amount": None,
        "mpesa_receipt_number": None,
        "phone_number": None,
        "transaction_date": None,
    }

    items = (stk_callback.get("CallbackMetadata") or {}).get("Item", [])
    lookup = {item.get("Name"): item.get("Value") for item in items}
    parsed["amount"] = lookup.get("Amount")
    parsed["mpesa_receipt_number"] = lookup.get("MpesaReceiptNumber")
    parsed["phone_number"] = lookup.get("PhoneNumber")
    parsed["transaction_date"] = lookup.get("TransactionDate")

    return parsed