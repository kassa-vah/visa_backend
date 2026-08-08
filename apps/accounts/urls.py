"""
apps/accounts/urls.py

Route structure for admin management. Mounted under /api/v1/admin/ in
config/urls.py.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdminRequestViewSet, MeView

router = DefaultRouter()
router.register("admin-requests", AdminRequestViewSet, basename="admin-request")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
] + router.urls