"""
apps/accounts/services.py

Business logic for AdminProfile status transitions.

Kept out of views.py deliberately: this makes the transition + audit-log
behavior unit-testable independent of HTTP/DRF plumbing, and reusable from
anywhere else that might need it later (a management command, an admin
action, etc.) without duplicating the logic.

Every transition here does two things atomically: (1) change status and
stamp the actor/timestamp, (2) write an ActivityLog entry. Neither happens
without the other — see the @transaction.atomic wrapper.
"""

from django.db import transaction
from django.utils import timezone

from apps.activitylog.models import ActivityLog

from .models import AdminProfile, AdminStatus


class InvalidTransition(Exception):
    """Raised when a requested status transition isn't valid from the
    profile's current status (e.g. approving an already-approved admin)."""


def _write_log(actor, action: str, admin_profile: AdminProfile, description: str):
    ActivityLog.objects.create(
        actor=actor,
        action=action,
        target_type="AdminProfile",
        target_id=str(admin_profile.id),
        description=description,
    )


@transaction.atomic
def approve_admin(actor, admin_profile: AdminProfile) -> AdminProfile:
    if admin_profile.status != AdminStatus.PENDING:
        raise InvalidTransition(f"Cannot approve an admin with status {admin_profile.status}.")

    admin_profile.status = AdminStatus.APPROVED
    admin_profile.approved_by = actor
    admin_profile.approved_at = timezone.now()
    admin_profile.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    _write_log(actor, "admin.approve", admin_profile, f"Approved admin request for {admin_profile.user_profile}.")
    return admin_profile


@transaction.atomic
def deny_admin(actor, admin_profile: AdminProfile) -> AdminProfile:
    if admin_profile.status != AdminStatus.PENDING:
        raise InvalidTransition(f"Cannot deny an admin with status {admin_profile.status}.")

    admin_profile.status = AdminStatus.DENIED
    admin_profile.denied_by = actor
    admin_profile.denied_at = timezone.now()
    admin_profile.save(update_fields=["status", "denied_by", "denied_at", "updated_at"])

    _write_log(actor, "admin.deny", admin_profile, f"Denied admin request for {admin_profile.user_profile}.")
    return admin_profile


@transaction.atomic
def suspend_admin(actor, admin_profile: AdminProfile) -> AdminProfile:
    if admin_profile.status != AdminStatus.APPROVED:
        raise InvalidTransition(f"Cannot suspend an admin with status {admin_profile.status}.")

    admin_profile.status = AdminStatus.SUSPENDED
    admin_profile.status_changed_by = actor
    admin_profile.status_changed_at = timezone.now()
    admin_profile.save(update_fields=["status", "status_changed_by", "status_changed_at", "updated_at"])

    _write_log(actor, "admin.suspend", admin_profile, f"Suspended admin {admin_profile.user_profile}.")
    return admin_profile


@transaction.atomic
def revoke_admin(actor, admin_profile: AdminProfile) -> AdminProfile:
    if admin_profile.status not in (AdminStatus.APPROVED, AdminStatus.SUSPENDED):
        raise InvalidTransition(f"Cannot revoke an admin with status {admin_profile.status}.")

    admin_profile.status = AdminStatus.REVOKED
    admin_profile.status_changed_by = actor
    admin_profile.status_changed_at = timezone.now()
    admin_profile.save(update_fields=["status", "status_changed_by", "status_changed_at", "updated_at"])

    _write_log(actor, "admin.revoke", admin_profile, f"Revoked admin {admin_profile.user_profile}.")
    return admin_profile