"""
apps/accounts/permissions/admin_permissions.py

DRF permission classes enforcing the AdminProfile authorization chain.

These are the backend's actual gate — per project rule, hiding a button on
the frontend is NEVER sufficient. Every protected endpoint must be guarded
by one of these (or an equivalent) server-side.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import AdminStatus, AdminRole


def _get_admin_profile(user):
    """
    Resolve the AdminProfile for a Django user, if any.

    Returns None if the user has no UserProfile, or no AdminProfile at all
    (i.e. a plain authenticated user who never requested admin access).
    """
    profile = getattr(user, "profile", None)
    if profile is None:
        return None
    return getattr(profile, "admin_profile", None)


class IsApprovedAdmin(BasePermission):
    """
    Allows access only to users with an AdminProfile whose status is
    APPROVED, regardless of role (ADMIN or SUPER_ADMIN both pass).
    """

    message = "An approved administrator account is required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        admin_profile = _get_admin_profile(request.user)
        return bool(admin_profile and admin_profile.status == AdminStatus.APPROVED)


class IsSuperAdmin(BasePermission):
    """
    Allows access only to APPROVED administrators with role=SUPER_ADMIN.

    Use this for admin-management endpoints: approve / deny / suspend /
    revoke / permission changes. A normal ADMIN must get 403 here.
    """

    message = "Super Admin privileges are required for this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        admin_profile = _get_admin_profile(request.user)
        return bool(
            admin_profile
            and admin_profile.status == AdminStatus.APPROVED
            and admin_profile.role == AdminRole.SUPER_ADMIN
        )
