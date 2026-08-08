"""
apps/accounts/serializers.py

Phase 1: minimal read-only serializers to support the admin-requests list
endpoint. Write-side validation for approve/deny/suspend/revoke happens in
the views/services layer, NOT by exposing role/status as client-writable
fields here — that would reopen the privilege-escalation hole described in
the spec (section 13).
"""

from rest_framework import serializers

from .models import AdminProfile, UserProfile


class UserProfileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "display_name", "firebase_uid", "created_at"]
        read_only_fields = fields


class AdminProfileSerializer(serializers.ModelSerializer):
    user_profile = UserProfileSummarySerializer(read_only=True)

    class Meta:
        model = AdminProfile
        fields = [
            "id",
            "user_profile",
            "role",
            "status",
            "approved_by",
            "approved_at",
            "denied_by",
            "denied_at",
            "status_changed_by",
            "status_changed_at",
            "created_at",
            "updated_at",
        ]
        # Every field is read-only through this serializer. Status/role
        # transitions are performed explicitly in the approve/deny/suspend/
        # revoke view actions, not via generic update.
        read_only_fields = fields
