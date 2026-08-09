from django.test import TestCase

from apps.giving.models import Donation, GivingType, Offering, PaymentMethod, PaymentStatus


class OfferingModelTests(TestCase):
    def test_defaults_to_pending(self):
        offering = Offering.objects.create(
            amount=500,
            giving_type=GivingType.TITHE,
            payment_method=PaymentMethod.MPESA,
            phone_number="0712345678",
        )
        self.assertEqual(offering.status, PaymentStatus.PENDING)
        self.assertEqual(offering.donor_name, "Anonymous")

    def test_mark_success_sets_receipt(self):
        offering = Offering.objects.create(
            amount=500,
            giving_type=GivingType.OFFERING,
            payment_method=PaymentMethod.MPESA,
            phone_number="0712345678",
            mpesa_checkout_request_id="ws_CO_1",
        )
        offering.mark_success(receipt="RCPT123", provider_response={"ok": True})
        offering.refresh_from_db()
        self.assertEqual(offering.status, PaymentStatus.SUCCESS)
        self.assertEqual(offering.mpesa_receipt_number, "RCPT123")

    def test_mark_failed(self):
        offering = Offering.objects.create(
            amount=500,
            giving_type=GivingType.OTHER,
            payment_method=PaymentMethod.PAYSTACK,
            donor_email="a@b.com",
            paystack_reference="ref-1",
        )
        offering.mark_failed(provider_response={"status": "failed"})
        offering.refresh_from_db()
        self.assertEqual(offering.status, PaymentStatus.FAILED)


class DonationModelTests(TestCase):
    def test_defaults_campaign_to_general(self):
        donation = Donation.objects.create(
            amount=1000,
            payment_method=PaymentMethod.PAYSTACK,
            donor_email="a@b.com",
            paystack_reference="ref-2",
        )
        self.assertEqual(donation.campaign, "general")

    def test_custom_campaign(self):
        donation = Donation.objects.create(
            amount=2500,
            campaign="building-fund",
            payment_method=PaymentMethod.MPESA,
            phone_number="0712345678",
        )
        self.assertEqual(donation.campaign, "building-fund")
        self.assertIn("building-fund", str(donation))