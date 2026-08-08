from django.apps import AppConfig
from django.conf import settings


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts & Admin Authorization"

    def ready(self):
        # Initialize the Firebase Admin SDK exactly once. Django's dev-server
        # autoreloader imports apps twice in some configurations, and
        # firebase_admin.initialize_app() raises if called twice with the
        # same app name — so guard on the existing app list rather than
        # relying on import-order luck.
        import firebase_admin

        if not firebase_admin._apps:
            from firebase_admin import credentials

            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)