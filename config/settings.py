"""
config/settings.py

Phase 1 settings. Keep this minimal and explicit — flesh out
Paystack/M-Pesa/Brevo config as those integrations are actually
built (see services/), not preemptively.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env into the process environment. Without this, every os.environ.get()
# call below silently falls back to its default — .env would be present on
# disk but never actually take effect.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    # Project apps
    "apps.accounts",
    "apps.activitylog",
    "apps.content",
    "apps.events",
    "apps.giving",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must sit above CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite")  # "sqlite" or "postgresql"

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "visa_db"),
            "USER": os.environ.get("DB_USER", "visa_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    # Local dev default — no separate DB server required. Switch to
    # postgresql by setting DB_ENGINE=postgresql in .env once you have
    # Postgres running (production should always use postgresql).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Firebase Admin SDK
#
# Points at the service account JSON downloaded from:
# Firebase console → Project settings → Service accounts → Generate new
# private key. Never commit that file — it's already covered by .gitignore.
# Actual SDK initialization happens once, in apps/accounts/apps.py, so it
# doesn't run twice under the dev-server autoreloader.
# ---------------------------------------------------------------------------
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    "FIREBASE_CREDENTIALS_PATH",
    str(BASE_DIR / "config" / "firebase-service-account.json"),
)

# ---------------------------------------------------------------------------
# CORS — allows the React/Vite frontend (running on a different port) to
# call this API during local development. Add your deployed frontend's
# origin here too once it exists.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

# If the frontend needs to send cookies/auth headers with credentials mode,
# keep this True. Firebase ID tokens go in the Authorization header, not
# cookies, so this is mostly a safe default rather than a hard requirement.
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# M-Pesa (Safaricom Daraja) — apps/giving + services/payments/mpesa.py
#
# Sandbox creds: https://developer.safaricom.co.ke
# MPESA_SHORTCODE/PASSKEY default to Safaricom's public sandbox till so
# `POST /offerings` works out of the box in dev; production MUST override
# all four via .env.
# ---------------------------------------------------------------------------
MPESA_ENV = os.environ.get("MPESA_ENV", "sandbox")  # "sandbox" or "production"
MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "")
MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", "174379")
MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY", "")
# Must be a publicly reachable HTTPS URL Safaricom can POST to (use ngrok
# in dev). Matches apps/giving/urls.py's "offerings/mpesa/callback" route.
MPESA_CALLBACK_URL = os.environ.get(
    "MPESA_CALLBACK_URL",
    "https://example.com/offerings/mpesa/callback",
)

# ---------------------------------------------------------------------------
# Paystack — apps/giving + services/payments/paystack.py
#
# Secret key stays server-side only; the matching public key
# (VITE_PAYSTACK_PUBLIC_KEY) lives in the frontend's .env, not here.
# ---------------------------------------------------------------------------
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")