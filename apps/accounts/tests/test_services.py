"""
apps/accounts/tests/test_services.py

Unit tests for the status-transition logic in apps/accounts/services.py —
independent of HTTP/DRF, per the docstring rationale in that module.
"""

import pytest

from apps.accounts import services
from apps.accounts.models import AdminStatus
from apps.activitylog.models import ActivityLog

from .factories import make_admin_profile, make_user_profile


@pytest.mark.django_db
class TestApproveAdmin:
    def test_approves_pending_admin_and_stamps_actor(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)

        services.approve_admin(actor, admin_profile)
        admin_profile.refresh_from_db()

        assert admin_profile.status == AdminStatus.APPROVED
        assert admin_profile.approved_by == actor
        assert admin_profile.approved_at is not None

    def test_writes_activity_log(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)

        services.approve_admin(actor, admin_profile)

        log = ActivityLog.objects.get(action="admin.approve")
        assert log.actor == actor
        assert log.target_id == str(admin_profile.id)

    def test_rejects_approving_a_non_pending_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.APPROVED)

        with pytest.raises(services.InvalidTransition):
            services.approve_admin(actor, admin_profile)


@pytest.mark.django_db
class TestDenyAdmin:
    def test_denies_pending_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)

        services.deny_admin(actor, admin_profile)
        admin_profile.refresh_from_db()

        assert admin_profile.status == AdminStatus.DENIED
        assert admin_profile.denied_by == actor

    def test_rejects_denying_an_approved_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.APPROVED)

        with pytest.raises(services.InvalidTransition):
            services.deny_admin(actor, admin_profile)


@pytest.mark.django_db
class TestSuspendAndRevoke:
    def test_suspends_approved_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.APPROVED)

        services.suspend_admin(actor, admin_profile)
        admin_profile.refresh_from_db()

        assert admin_profile.status == AdminStatus.SUSPENDED
        assert admin_profile.status_changed_by == actor

    def test_rejects_suspending_a_pending_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)

        with pytest.raises(services.InvalidTransition):
            services.suspend_admin(actor, admin_profile)

    def test_revokes_approved_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.APPROVED)

        services.revoke_admin(actor, admin_profile)
        admin_profile.refresh_from_db()

        assert admin_profile.status == AdminStatus.REVOKED

    def test_revokes_suspended_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.SUSPENDED)

        services.revoke_admin(actor, admin_profile)
        admin_profile.refresh_from_db()

        assert admin_profile.status == AdminStatus.REVOKED

    def test_rejects_revoking_a_pending_admin(self):
        actor = make_user_profile("Super Admin").user
        admin_profile = make_admin_profile(status=AdminStatus.PENDING)

        with pytest.raises(services.InvalidTransition):
            services.revoke_admin(actor, admin_profile)