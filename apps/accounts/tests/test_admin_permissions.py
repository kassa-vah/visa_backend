"""
apps/accounts/tests/test_admin_permissions.py

API-level permission matrix for the admin-requests endpoints, mirroring
the test cases enumerated in the architecture spec (section 18).

Uses APIClient.force_authenticate to set request.user directly rather
than going through FirebaseAuthentication — these tests are about DRF
permission/view logic, not Firebase token verification (that has its own
coverage in test_authentication.py).
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AdminRole, AdminStatus

from .factories import make_admin_profile, make_user_profile


@pytest.fixture
def api_client():
    return APIClient()


LIST_URL = "/api/v1/admin/admin-requests/"


def detail_url(admin_profile_id):
    return f"{LIST_URL}{admin_profile_id}/"


def action_url(admin_profile_id, action_name):
    return f"{LIST_URL}{admin_profile_id}/{action_name}/"


@pytest.mark.django_db
class TestAdminDashboardAccess:
    def test_unauthenticated_user_gets_401(self, api_client):
        response = api_client.get(LIST_URL)
        assert response.status_code == 401

    def test_authenticated_user_without_admin_profile_gets_403(self, api_client):
        user = make_user_profile().user
        api_client.force_authenticate(user=user)

        response = api_client.get(LIST_URL)
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "status_value",
        [AdminStatus.PENDING, AdminStatus.DENIED, AdminStatus.SUSPENDED, AdminStatus.REVOKED],
    )
    def test_non_approved_admin_gets_403(self, api_client, status_value):
        admin_profile = make_admin_profile(status=status_value)
        api_client.force_authenticate(user=admin_profile.user_profile.user)

        response = api_client.get(LIST_URL)
        assert response.status_code == 403

    def test_approved_admin_gets_200(self, api_client):
        admin_profile = make_admin_profile(status=AdminStatus.APPROVED)
        api_client.force_authenticate(user=admin_profile.user_profile.user)

        response = api_client.get(LIST_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestSelfRequestCreation:
    def test_authenticated_user_can_request_admin_access(self, api_client):
        user = make_user_profile().user
        api_client.force_authenticate(user=user)

        response = api_client.post(LIST_URL)

        assert response.status_code == 201
        assert response.data["role"] == AdminRole.ADMIN
        assert response.data["status"] == AdminStatus.PENDING

    def test_cannot_request_twice(self, api_client):
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)
        api_client.force_authenticate(user=admin_profile.user_profile.user)

        response = api_client.post(LIST_URL)
        assert response.status_code == 409

    def test_request_body_cannot_set_role_or_status(self, api_client):
        # Even if a client sends role/status in the body, the created
        # profile must come out as the model defaults (ADMIN / PENDING) —
        # see spec section 13, privilege escalation.
        user = make_user_profile().user
        api_client.force_authenticate(user=user)

        response = api_client.post(
            LIST_URL, {"role": AdminRole.SUPER_ADMIN, "status": AdminStatus.APPROVED}
        )

        assert response.status_code == 201
        assert response.data["role"] == AdminRole.ADMIN
        assert response.data["status"] == AdminStatus.PENDING


@pytest.mark.django_db
class TestSuperAdminManagementActions:
    def test_normal_admin_cannot_approve_gets_403(self, api_client):
        acting_admin = make_admin_profile(status=AdminStatus.APPROVED, role=AdminRole.ADMIN)
        target = make_admin_profile(status=AdminStatus.PENDING)
        api_client.force_authenticate(user=acting_admin.user_profile.user)

        response = api_client.post(action_url(target.id, "approve"))
        assert response.status_code == 403

    def test_super_admin_can_approve(self, api_client):
        super_admin = make_admin_profile(status=AdminStatus.APPROVED, role=AdminRole.SUPER_ADMIN)
        target = make_admin_profile(status=AdminStatus.PENDING)
        api_client.force_authenticate(user=super_admin.user_profile.user)

        response = api_client.post(action_url(target.id, "approve"))

        assert response.status_code == 200
        target.refresh_from_db()
        assert target.status == AdminStatus.APPROVED

    def test_super_admin_cannot_approve_own_request(self, api_client):
        super_admin = make_admin_profile(status=AdminStatus.APPROVED, role=AdminRole.SUPER_ADMIN)
        api_client.force_authenticate(user=super_admin.user_profile.user)

        response = api_client.post(action_url(super_admin.id, "approve"))
        assert response.status_code == 403

    def test_super_admin_cannot_revoke_own_access(self, api_client):
        super_admin = make_admin_profile(status=AdminStatus.APPROVED, role=AdminRole.SUPER_ADMIN)
        api_client.force_authenticate(user=super_admin.user_profile.user)

        response = api_client.post(action_url(super_admin.id, "revoke"))
        assert response.status_code == 403

    def test_approving_already_approved_admin_returns_400(self, api_client):
        super_admin = make_admin_profile(status=AdminStatus.APPROVED, role=AdminRole.SUPER_ADMIN)
        target = make_admin_profile(status=AdminStatus.APPROVED)
        api_client.force_authenticate(user=super_admin.user_profile.user)

        response = api_client.post(action_url(target.id, "approve"))
        assert response.status_code == 400