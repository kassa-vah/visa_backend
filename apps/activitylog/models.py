"""
apps/activitylog/models.py

Audit trail for administrative decisions and other sensitive actions
(admin approvals/denials/suspensions/revocations, permission grants, etc).

Kept as its own app (rather than bolted onto accounts) because activity
logging will likely end up capturing events from content/events/giving apps
too as those are built out in later phases.
"""

import uuid

from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="Who performed the action. Null if system-initiated.",
    )

    action = models.CharField(
        max_length=64,
        help_text="Short machine-readable verb, e.g. 'admin.approve', 'admin.suspend'.",
    )

    # Generic-ish target reference. Kept simple (no GenericForeignKey yet) —
    # revisit with contenttypes if/when logging needs to span many models.
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)

    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor} :: {self.action} :: {self.target_type}:{self.target_id}"
