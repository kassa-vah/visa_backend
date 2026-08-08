"""
apps/accounts/views.py

Admin-request management API.

    GET  /api/v1/admin/admin-requests/            list  (any approved admin)
    GET  /api/v1/admin/admin-requests/<id>/        retrieve (any approved admin)
    POST /api/v1/admin/admin-requests/              create — self-request admin access
    POST /api/v1/admin/admin-requests/<id>/approve/  (Super Admin only)
    POST /api/v1/admin/admin-requests/<id>/deny/     (Super Admin only)
    POST /api/v1/admin/admin-requests/<id>/suspend/  (Super Admin only)
    POST /api/v1/admin/admin-requests/<id>/revoke/   (Super Admin only)

Deliberately built on GenericViewSet + explicit mixins (List, Retrieve,
Create) rather than ModelViewSet: there is intentionally no generic
update/destroy route. Role/status must only ever change through the named
transition actions below, which apply the InvalidTransition guard and
write an ActivityLog entry — never through a raw PATCH that could smuggle
in a role/status field (see spec section 13, privilege escalation).
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import AdminProfile
from .permissions import IsApprovedAdmin, IsSuperAdmin
from .serializers import AdminProfileSerializer


class AdminRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AdminProfile.objects.select_related("user_profile").all()
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsApprovedAdmin]

    def get_permissions(self):
        if self.action in {"approve", "deny", "suspend", "revoke"}:
            return [IsAuthenticated(), IsSuperAdmin()]
        if self.action == "create":
            # Any authenticated Firebase user may request admin access —
            # they aren't an admin yet, so IsApprovedAdmin would always
            # reject them.
            return [IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        user_profile = getattr(request.user, "profile", None)
        if user_profile is None:
            return Response(
                {"detail": "No profile is associated with this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(user_profile, "admin_profile"):
            return Response(
                {"detail": "An admin request already exists for this account."},
                status=status.HTTP_409_CONFLICT,
            )

        # role/status are never taken from the request body — every new
        # request starts as role=ADMIN, status=PENDING per the model
        # defaults, full stop.
        admin_profile = AdminProfile.objects.create(user_profile=user_profile)
        serializer = self.get_serializer(admin_profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _run_transition(self, request, pk, transition_fn, self_action_error):
        admin_profile = self.get_object()

        actor_profile = getattr(request.user, "profile", None)
        if actor_profile is not None and actor_profile.pk == admin_profile.user_profile_id:
            # A Super Admin acting on their own AdminProfile — even via the
            # legitimate endpoint — is exactly the self-promotion pattern
            # the spec calls out (section 7/13). Block it here rather than
            # relying on the UI to hide the button.
            return Response({"detail": self_action_error}, status=status.HTTP_403_FORBIDDEN)

        try:
            transition_fn(request.user, admin_profile)
        except services.InvalidTransition as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(admin_profile)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._run_transition(
            request, pk, services.approve_admin, "You cannot approve your own admin request."
        )

    @action(detail=True, methods=["post"])
    def deny(self, request, pk=None):
        return self._run_transition(
            request, pk, services.deny_admin, "You cannot deny your own admin request."
        )

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._run_transition(
            request, pk, services.suspend_admin, "You cannot suspend your own admin access."
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        return self._run_transition(
            request, pk, services.revoke_admin, "You cannot revoke your own admin access."
        )