"""
apps/accounts/tests/test_authentication.py

Tests for FirebaseAuthentication. Mocks services.firebase.client.verify_id_token
at the boundary rather than hitting real Firebase — these tests are about
"given a decoded token, does the right Django user get resolved/created",
not about Firebase SDK behavior itself.
"""

from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory

from apps.accounts.authentication import FirebaseAuthentication
from apps.accounts.models import UserProfile
from services.firebase.client import FirebaseTokenError


def _request_with_bearer(token="fake-token"):
    factory = APIRequestFactory()
    return factory.get("/api/v1/admin/admin-requests/", HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
class TestFirebaseAuthentication:
    def test_no_auth_header_returns_none(self):
        factory = APIRequestFactory()
        request = factory.get("/api/v1/admin/admin-requests/")

        result = FirebaseAuthentication().authenticate(request)
        assert result is None

    @patch("apps.accounts.authentication.verify_id_token")
    def test_invalid_token_raises_authentication_failed(self, mock_verify):
        from rest_framework.exceptions import AuthenticationFailed

        mock_verify.side_effect = FirebaseTokenError("token expired")
        request = _request_with_bearer()

        with pytest.raises(AuthenticationFailed):
            FirebaseAuthentication().authenticate(request)

    @patch("apps.accounts.authentication.verify_id_token")
    def test_valid_token_creates_user_profile_on_first_login(self, mock_verify):
        mock_verify.return_value = {
            "uid": "new-firebase-uid",
            "email": "person@example.com",
            "name": "Person Example",
        }
        request = _request_with_bearer()

        user, _ = FirebaseAuthentication().authenticate(request)

        profile = UserProfile.objects.get(firebase_uid="new-firebase-uid")
        assert profile.user == user
        assert profile.display_name == "Person Example"

    @patch("apps.accounts.authentication.verify_id_token")
    def test_valid_token_reuses_existing_user_profile(self, mock_verify):
        mock_verify.return_value = {"uid": "existing-uid", "email": "e@example.com"}
        request = _request_with_bearer()

        user_first, _ = FirebaseAuthentication().authenticate(request)
        user_second, _ = FirebaseAuthentication().authenticate(request)

        assert user_first.pk == user_second.pk
        assert UserProfile.objects.filter(firebase_uid="existing-uid").count() == 1

    @patch("apps.accounts.authentication.verify_id_token")
    def test_token_missing_uid_raises_authentication_failed(self, mock_verify):
        from rest_framework.exceptions import AuthenticationFailed

        mock_verify.return_value = {"email": "no-uid@example.com"}
        request = _request_with_bearer()

        with pytest.raises(AuthenticationFailed):
            FirebaseAuthentication().authenticate(request)