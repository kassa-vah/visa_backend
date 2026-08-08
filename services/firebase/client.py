"""
services/firebase/client.py

Thin wrapper around the Firebase Admin SDK for verifying ID tokens.

Configuration (see .env.example) — set exactly one of:
    FIREBASE_CREDENTIALS_PATH   Path to a service-account JSON file
    FIREBASE_CREDENTIALS_JSON   The service-account JSON itself, inline

The Firebase app is initialized lazily on first use, so importing this
module — or starting the server without credentials configured — never
fails by itself. It only raises once someone actually tries to verify a
token, which is the point at which credentials are genuinely required.
"""

import json
import os

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

_app = None


class FirebaseTokenError(Exception):
    """Raised when a Firebase ID token fails verification, or Firebase
    itself isn't configured. Callers (see apps/accounts/authentication.py)
    treat this uniformly as "authentication failed" — they don't need to
    distinguish "bad token" from "server misconfigured" to respond
    correctly with a 401."""


def _get_app():
    global _app
    if _app is not None:
        return _app

    if firebase_admin._apps:
        _app = firebase_admin.get_app()
        return _app

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

    if cred_path:
        cred = credentials.Certificate(cred_path)
    elif cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        raise FirebaseTokenError(
            "Firebase is not configured: set FIREBASE_CREDENTIALS_PATH or "
            "FIREBASE_CREDENTIALS_JSON in the environment."
        )

    _app = firebase_admin.initialize_app(cred)
    return _app


def verify_id_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return its decoded claims (includes
    'uid', and where available 'email' / 'name').

    Raises FirebaseTokenError on any verification failure — expired,
    malformed, revoked token, or Firebase not configured.
    """
    try:
        app = _get_app()
        return firebase_auth.verify_id_token(id_token, app=app)
    except FirebaseTokenError:
        raise
    except Exception as exc:
        # firebase_admin raises several distinct exception types
        # (ExpiredIdTokenError, InvalidIdTokenError, RevokedIdTokenError,
        # ...) — collapse them to one error type at this boundary so
        # callers only need to handle FirebaseTokenError.
        raise FirebaseTokenError(f"Firebase token verification failed: {exc}") from exc