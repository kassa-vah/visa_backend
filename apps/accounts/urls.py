"""
apps/accounts/urls.py

Route structure for admin management. Mounted under /api/v1/admin/ in
config/urls.py.
"""

from rest_framework.routers import DefaultRouter

from .views import AdminRequestViewSet

router = DefaultRouter()
router.register("admin-requests", AdminRequestViewSet, basename="admin-request")

urlpatterns = router.urls
