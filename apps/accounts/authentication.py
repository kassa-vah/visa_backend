"""
apps/accounts/authentication.py

DRF authentication class implementing the login flow's identity half
(architecture spec, sections 14/15):

    "Firebase Authentication" answers "Who are you?"
    This class turns that answer into a Django User + UserProfile.

Expects a request header of the form:

    Authorization: Bearer <firebase_id_token>

On success, resolves — or lazily creates — the matching UserProfile keyed
on the token's Firebase UID.

Deliberately does NOT create or touch AdminProfile here. Getting a
UserProfile just proves "this person is a known, Firebase-authenticated
user." Becoming an admin candidate is a separate, explicit action (see
AdminRequestViewSet.create in views.py) — never an automatic side effect
of logging in. Conflating the two would undermine the whole point of the
AdminProfile approval gate.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import authentication, exceptions

from services.firebase.client import FirebaseTokenError, verify_id_token

from .models import UserProfile

User = get_user_model()


class FirebaseAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate_header(self, request):
        # Required so DRF's exception handling returns 401 Unauthorized for
        # missing/invalid credentials rather than defaulting to 403
        # Forbidden (DRF only emits 401 when at least one configured
        # authenticator declares a challenge scheme here). The spec's test
        # matrix (section 18) requires 401 for the unauthenticated case.
        return self.keyword

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header or not auth_header.startswith(f"{self.keyword} "):
            # No bearer token present — defer to other configured
            # authentication classes (or AnonymousUser) rather than
            # rejecting outright, per DRF convention.
            return None

        id_token = auth_header[len(self.keyword) + 1 :].strip()
        if not id_token:
            raise exceptions.AuthenticationFailed("Empty bearer token.")

        try:
            decoded = verify_id_token(id_token)
        except FirebaseTokenError as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc

        uid = decoded.get("uid") or decoded.get("user_id")
        if not uid:
            raise exceptions.AuthenticationFailed("Firebase token missing uid claim.")

        user = self._get_or_create_user(uid, decoded)
        return (user, None)

    @transaction.atomic
    def _get_or_create_user(self, uid: str, decoded: dict):
        try:
            return UserProfile.objects.select_related("user").get(firebase_uid=uid).user
        except UserProfile.DoesNotExist:
            pass

        email = decoded.get("email") or ""
        display_name = decoded.get("name", "")

        # Django's default User requires a unique username. Prefer email
        # when present and free; fall back to the Firebase UID so two
        # accounts can never collide.
        username = email if email and not User.objects.filter(username=email).exists() else uid

        user = User.objects.create(username=username, email=email)
        UserProfile.objects.create(user=user, firebase_uid=uid, display_name=display_name)
        return user