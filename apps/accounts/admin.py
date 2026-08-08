from django.contrib import admin

from .models import AdminProfile, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "firebase_uid", "user", "created_at")
    search_fields = ("display_name", "firebase_uid", "user__username", "user__email")


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user_profile", "role", "status", "approved_by", "approved_at")
    list_filter = ("role", "status")
    search_fields = ("user_profile__display_name", "user_profile__firebase_uid")

    # NOTE: this is the Django Admin panel — a separate, internal-only
    # surface (see spec section 8/9). Access to /admin/ itself is still
    # gated by Django's own is_staff/is_superuser, which are NEVER set
    # automatically just because someone has an AdminProfile.
