"""
apps/accounts/models.py

Core identity + admin authorization models for the VISA platform.

Architecture (see project spec):
    Firebase Authentication  ->  "Who are you?"
    UserProfile              ->  Django-side identity record linked to a Firebase UID
    AdminProfile             ->  "What are you allowed to do?" (separate, optional record)

IMPORTANT:
    - A Django `User` having an AdminProfile with role=SUPER_ADMIN does NOT imply
      `is_staff` / `is_superuser`. Those control Django Admin (/admin/) access and
      are intentionally a SEPARATE authorization system. Never couple them here.
    - Role/status changes must only ever happen through protected backend
      operations (see apps/accounts/services.py, once implemented) — never
      directly from client-supplied data.
"""

import uuid

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """
    Django-side identity record for a person authenticated via Firebase.

    This is created for every authenticated person (admin candidates and
    regular/public users alike). It does NOT grant any administrative
    capability on its own — see AdminProfile for that.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Firebase is the identity source of truth; we mirror the UID here so we
    # can resolve "Firebase token -> Django user" without re-hitting Firebase
    # on every request.
    firebase_uid = models.CharField(max_length=128, unique=True, db_index=True)

    display_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return self.display_name or self.firebase_uid


class AdminRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"


class AdminStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    DENIED = "DENIED", "Denied"
    SUSPENDED = "SUSPENDED", "Suspended"
    REVOKED = "REVOKED", "Revoked"


class AdminProfile(models.Model):
    """
    Administrative privilege record.

    A UserProfile becomes an "admin candidate" by having one of these created
    with status=PENDING. Only an approved (status=APPROVED) AdminProfile
    grants access to the React Admin Dashboard's protected API endpoints —
    and even then, only according to `role` and whatever granular
    permissions are layered on top later.

    This model intentionally has NO relationship to Django's is_staff /
    is_superuser fields. Those are configured separately and manually,
    per project rule: VISA SUPER ADMIN != DJANGO SUPERUSER.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="admin_profile",
    )

    role = models.CharField(
        max_length=32,
        choices=AdminRole.choices,
        default=AdminRole.ADMIN,
    )
    status = models.CharField(
        max_length=32,
        choices=AdminStatus.choices,
        default=AdminStatus.PENDING,
        db_index=True,
    )

    # Audit trail — who made the approval/denial decision, and when.
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admins_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admins_denied",
    )
    denied_at = models.DateTimeField(null=True, blank=True)

    # Set on suspend/revoke actions; kept generic so both can reuse it rather
    # than growing a field per action. Extend later if a distinct actor/time
    # per action becomes necessary.
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_status_changes",
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admin Profile"
        verbose_name_plural = "Admin Profiles"

    def __str__(self):
        return f"{self.user_profile} [{self.role} / {self.status}]"

    @property
    def is_approved(self) -> bool:
        return self.status == AdminStatus.APPROVED

    @property
    def is_super_admin(self) -> bool:
        return self.is_approved and self.role == AdminRole.SUPER_ADMIN
