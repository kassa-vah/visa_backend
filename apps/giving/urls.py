from django.urls import path

from . import views

app_name = "giving"

urlpatterns = [
    # Offerings (tithe / offering / thanksgiving / other) — matches Offerings.jsx
    path("offerings", views.OfferingCreateView.as_view(), name="offering-create"),
    path("offerings/verify", views.OfferingVerifyView.as_view(), name="offering-verify"),
    path("offerings/<uuid:pk>", views.OfferingDetailView.as_view(), name="offering-detail"),

    # Donations (campaign-based giving)
    path("donations", views.DonationCreateView.as_view(), name="donation-create"),
    path("donations/verify", views.DonationVerifyView.as_view(), name="donation-verify"),
    path("donations/<uuid:pk>", views.DonationDetailView.as_view(), name="donation-detail"),

    # Webhooks
    path("offerings/mpesa/callback", views.MpesaCallbackView.as_view(), name="mpesa-callback"),
    path("payments/paystack/webhook", views.PaystackWebhookView.as_view(), name="paystack-webhook"),
]