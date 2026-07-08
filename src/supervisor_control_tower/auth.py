from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib import response
from urllib.parse import urlencode

import requests

from supervisor_control_tower.config import Settings
from supervisor_control_tower.models import AppUser

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def demo_user() -> AppUser:
    return AppUser(
        google_subject_id="demo-local-user",
        email="demo.user@example.com",
        display_name="Demo User",
        profile_image_url=None,
    )


def build_google_auth_url(settings: Settings) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
        "access_type": "online",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def new_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def exchange_code_for_user(settings: Settings, code: str) -> AppUser:
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_redirect_uri,
        },
        timeout=15,
    )
    # response.raise_for_status()
    # token_payload = response.json()
    if not response.ok:
        raise ValueError(
            f"Google token exchange failed with status {response.status_code}: "
            f"{response.text[:500]}"
        )

    token_payload = response.json()
    id_token = token_payload.get("id_token")
    if not id_token:
        raise ValueError("Google did not return an id_token.")
    claims = _decode_unverified_jwt(id_token)
    return AppUser(
        google_subject_id=str(claims["sub"]),
        email=str(claims.get("email", "")),
        display_name=str(claims.get("name") or claims.get("email") or "Google User"),
        profile_image_url=claims.get("picture"),
    )


def _decode_unverified_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid id_token format.")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
