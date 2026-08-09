from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.giving.models import Donation, GivingType, Offering, PaymentStatus
from services.payments.mpesa import MpesaError
from services.payments.paystack import PaystackError


class OfferingMpesaCreateTests(APITestCase):
    @patch("apps.giving.views.initiate_stk_push")
    def test_successful_stk_push_creates_pending_offering(self, mock_stk):
        mock_stk.return_value = {
            "CheckoutRequestID": "ws_CO_123",
            "MerchantRequestID": "mr_123",
            "ResponseCode": "0",
        }
        resp = self.client.post(
            reverse("giving:offering-create"),
            {
                "amount": "500",
                "payment_method": "mpesa",
                "giving_type": "tithe",
                "donor_name": "Jane",
                "phone_number": "0712345678",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        offering = Offering.objects.get()
        self.assertEqual(offering.status, PaymentStatus.PENDING)
        self.assertEqual(offering.mpesa_checkout_request_id, "ws_CO_123")

    @patch("apps.giving.views.initiate_stk_push", side_effect=MpesaError("Daraja down"))
    def test_daraja_failure_marks_offering_failed(self, mock_stk):
        resp = self.client.post(
            reverse("giving:offering-create"),
            {
                "amount": "500",
                "payment_method": "mpesa",
                "giving_type": "tithe",
                "phone_number": "0712345678",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(Offering.objects.get().status, PaymentStatus.FAILED)

    def test_invalid_phone_number_rejected(self):
        resp = self.client.post(
            reverse("giving:offering-create"),
            {"amount": "500", "payment_method": "mpesa", "giving_type": "tithe", "phone_number": "12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Offering.objects.count(), 0)


class OfferingPaystackVerifyTests(APITestCase):
    @patch("apps.giving.views.verify_transaction")
    def test_successful_verification_marks_offering_success(self, mock_verify):
        mock_verify.return_value = {"status": "success", "amount": 50000, "reference": "ref-1"}
        resp = self.client.post(
            reverse("giving:offering-verify"),
            {
                "reference": "ref-1",
                "amount": "500",
                "giving_type": "thanksgiving",
                "donor_email": "a@b.com",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Offering.objects.get().status, PaymentStatus.SUCCESS)

    @patch("apps.giving.views.verify_transaction")
    def test_amount_mismatch_is_rejected(self, mock_verify):
        # Verified amount (200 KES) doesn't match what was requested (500 KES).
        mock_verify.return_value = {"status": "success", "amount": 20000, "reference": "ref-2"}
        resp = self.client.post(
            reverse("giving:offering-verify"),
            {"reference": "ref-2", "amount": "500", "giving_type": "other", "donor_email": "a@b.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Offering.objects.get().status, PaymentStatus.FAILED)

    @patch("apps.giving.views.verify_transaction", side_effect=PaystackError("bad reference"))
    def test_paystack_error_bubbles_up(self, mock_verify):
        resp = self.client.post(
            reverse("giving:offering-verify"),
            {"reference": "bad-ref", "amount": "500", "giving_type": "other", "donor_email": "a@b.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 502)


class DonationEndpointsTests(APITestCase):
    @patch("apps.giving.views.initiate_stk_push")
    def test_donation_mpesa_create_defaults_campaign(self, mock_stk):
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_9", "MerchantRequestID": "mr_9", "ResponseCode": "0"}
        resp = self.client.post(
            reverse("giving:donation-create"),
            {"amount": "1000", "payment_method": "mpesa", "phone_number": "0712345678"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Donation.objects.get().campaign, "general")


class MpesaCallbackTests(APITestCase):
    def test_successful_callback_marks_offering_success(self):
        offering = Offering.objects.create(
            amount=500,
            giving_type=GivingType.TITHE,
            payment_method="mpesa",
            phone_number="0712345678",
            mpesa_checkout_request_id="ws_CO_555",
        )
        callback_body = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "mr_555",
                    "CheckoutRequestID": "ws_CO_555",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 500},
                            {"Name": "MpesaReceiptNumber", "Value": "RCPT999"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        resp = self.client.post(reverse("giving:mpesa-callback"), callback_body, format="json")
        self.assertEqual(resp.status_code, 200)
        offering.refresh_from_db()
        self.assertEqual(offering.status, PaymentStatus.SUCCESS)
        self.assertEqual(offering.mpesa_receipt_number, "RCPT999")