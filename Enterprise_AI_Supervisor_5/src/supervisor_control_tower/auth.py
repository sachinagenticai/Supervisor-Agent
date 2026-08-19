from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode

import requests
import jwt
from cryptography.fernet import Fernet, InvalidToken
from jwt import PyJWKClient

from supervisor_control_tower.config import Settings
from supervisor_control_tower.models import AppUser

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"


def validate_google_oauth_settings(settings: Settings) -> None:
    """Validate the custom Google OAuth configuration loaded from environment.

    The application intentionally uses the same configuration style as the
    original Supervisor Agent implementation: GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI are read through ``Settings``.
    Local development normally supplies them through ``.env``. Streamlit Cloud
    supplies the same top-level names through its Secrets dashboard.
    """

    missing: list[str] = []
    if not str(settings.google_client_id or "").strip():
        missing.append("GOOGLE_CLIENT_ID")
    if not str(settings.google_client_secret or "").strip():
        missing.append("GOOGLE_CLIENT_SECRET")
    if not str(settings.google_redirect_uri or "").strip():
        missing.append("GOOGLE_REDIRECT_URI")

    if missing:
        raise ValueError("Missing Google OAuth setting(s): " + ", ".join(missing))

    redirect_uri = settings.google_redirect_uri.strip()
    if not redirect_uri.startswith(("http://", "https://")):
        raise ValueError("GOOGLE_REDIRECT_URI must be an absolute HTTP or HTTPS URL.")



def _oauth_state_cipher(settings: Settings) -> Fernet:
    """Derive a stable encryption key without introducing another secret."""

    validate_google_oauth_settings(settings)
    material = (
        f"{settings.google_client_id}:{settings.google_client_secret}:"
        "enterprise-ai-supervisor-oauth-state-v1"
    ).encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)


def create_oauth_state(settings: Settings, code_verifier: str) -> str:
    """Create an encrypted, time-stamped OAuth state containing the PKCE verifier.

    Streamlit may create a fresh WebSocket session after returning from Google.
    Keeping the verifier inside an authenticated encrypted state token makes the
    callback independent of in-memory session state while preserving CSRF and
    PKCE protections.
    """

    payload = json.dumps(
        {"nonce": secrets.token_urlsafe(24), "code_verifier": code_verifier},
        separators=(",", ":"),
    ).encode("utf-8")
    return _oauth_state_cipher(settings).encrypt(payload).decode("ascii")


def read_oauth_state(
    settings: Settings,
    state: str,
    *,
    max_age_seconds: int = 600,
) -> str:
    """Validate/decrypt OAuth state and return its PKCE code verifier."""

    try:
        raw = _oauth_state_cipher(settings).decrypt(
            state.encode("ascii"),
            ttl=max_age_seconds,
        )
        payload = json.loads(raw.decode("utf-8"))
    except (InvalidToken, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("OAuth state is invalid or expired. Start sign-in again.") from exc

    verifier = str(payload.get("code_verifier") or "").strip()
    nonce = str(payload.get("nonce") or "").strip()
    if len(verifier) < 43 or not nonce:
        raise ValueError("OAuth state payload is incomplete. Start sign-in again.")
    return verifier


def new_pkce_pair() -> tuple[str, str]:
    """Return a PKCE code verifier and S256 code challenge."""

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def build_google_auth_url(
    settings: Settings,
    *,
    state: str,
    code_challenge: str,
) -> str:
    """Build the Google authorization URL for the custom OAuth flow."""

    validate_google_oauth_settings(settings)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
        "access_type": "online",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_user(
    settings: Settings,
    *,
    code: str,
    code_verifier: str,
) -> AppUser:
    """Exchange Google's authorization code and verify the returned ID token.

    This keeps the original application's custom OAuth shape while correcting
    its earlier unverified-JWT behaviour. Google's signing keys, issuer,
    audience and expiry are verified with Google's published JWKS before an
    application user is created.
    """

    validate_google_oauth_settings(settings)

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
            timeout=settings.google_oauth_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise ValueError("Unable to reach Google token endpoint.") from exc

    if not response.ok:
        detail = response.text[:500].replace("\n", " ")
        raise ValueError(
            f"Google token exchange failed with status {response.status_code}: {detail}"
        )

    try:
        token_payload = response.json()
    except ValueError as exc:
        raise ValueError("Google token endpoint returned invalid JSON.") from exc

    raw_id_token = token_payload.get("id_token")
    if not raw_id_token:
        raise ValueError("Google did not return an ID token.")

    try:
        signing_key = PyJWKClient(
            GOOGLE_JWKS_URL, timeout=settings.google_oauth_timeout_seconds
        ).get_signing_key_from_jwt(raw_id_token)
        claims = jwt.decode(
            raw_id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=["accounts.google.com", "https://accounts.google.com"],
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception as exc:
        raise ValueError("Google ID token verification failed.") from exc

    if claims.get("email_verified") is not True:
        raise ValueError("Google account email is not verified.")

    email = str(claims.get("email") or "").strip().lower()
    subject = str(claims.get("sub") or "").strip()
    if not email or not subject:
        raise ValueError("Google ID token is missing required identity claims.")

    return AppUser(
        google_subject_id=subject,
        email=email,
        display_name=str(claims.get("name") or email).strip(),
        profile_image_url=(
            str(claims.get("picture")) if claims.get("picture") else None
        ),
    )
