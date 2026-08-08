"""
apps/accounts/tests/factories.py

Small helpers for building User/UserProfile/AdminProfile fixtures in
tests, without pulling in a full factory library for what's currently a
handful of models.
"""

import itertools

from django.contrib.auth import get_user_model

from apps.accounts.models import AdminProfile, AdminRole, AdminStatus, UserProfile

User = get_user_model()
_counter = itertools.count()


def make_user_profile(display_name="Test User"):
    n = next(_counter)
    user = User.objects.create(username=f"user{n}", email=f"user{n}@example.com")
    return UserProfile.objects.create(
        user=user, firebase_uid=f"firebase-uid-{n}", display_name=display_name
    )


def make_admin_profile(
    display_name="Test Admin",
    role=AdminRole.ADMIN,
    status=AdminStatus.PENDING,
):
    user_profile = make_user_profile(display_name)
    return AdminProfile.objects.create(user_profile=user_profile, role=role, status=status)