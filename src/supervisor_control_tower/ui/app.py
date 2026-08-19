from __future__ import annotations

import json
import logging
import os
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from supervisor_control_tower.auth import (
    build_google_auth_url,
    create_oauth_state,
    exchange_code_for_user,
    new_pkce_pair,
    read_oauth_state,
    validate_google_oauth_settings,
)
from supervisor_control_tower.config import get_settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AppUser
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import brand_wordmark, inject_css
from supervisor_control_tower.ui.pages import dashboard, evaluate, glossary, history

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)


def get_database() -> Database:
    if "database" not in st.session_state:
        st.session_state.database = Database(get_settings())
    return st.session_state.database


def persist_login(user: AppUser) -> AppUser:
    database = get_database()
    with database.transaction() as connection:
        repository = SupervisorRepository(connection)
        db_user = repository.upsert_user(user)
        repository.add_audit_event(
            None,
            db_user.id,
            "sign_in",
            {"email": db_user.email, "provider": "google"},
        )
        return db_user


def _single_query_value(name: str) -> str | None:
    """Read one callback query parameter across Streamlit versions."""

    value: Any = st.query_params.get(name)
    if isinstance(value, list):
        value = value[0] if value else None
    text = str(value or "").strip()
    return text or None


def _clear_oauth_session() -> None:
    for key in (
        "oauth_auth_url",
        "oauth_redirect_attempted",
    ):
        st.session_state.pop(key, None)


def _prepare_google_authorization() -> str:
    settings = get_settings()
    verifier, challenge = new_pkce_pair()
    state = create_oauth_state(settings, verifier)
    auth_url = build_google_auth_url(
        settings,
        state=state,
        code_challenge=challenge,
    )
    st.session_state["oauth_auth_url"] = auth_url
    return auth_url


def _render_google_redirect(auth_url: str, error_message: str | None = None) -> None:
    """Redirect to Google immediately and keep a visible fallback button."""

    st.markdown(
        """
        <div style="max-width:620px;margin:12vh auto 0;text-align:center;">
          <h1 style="font-size:36px;margin-bottom:10px;">Enterprise AI Supervisor</h1>
          <p style="font-size:16px;color:#64748b;margin-bottom:28px;">
            Sign in securely with your Google account to continue.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if error_message:
        st.error(error_message)

    st.link_button(
        "Continue with Google",
        auth_url,
        type="primary",
        use_container_width=True,
    )

    if not error_message and not st.session_state.get("oauth_redirect_attempted"):
        st.session_state["oauth_redirect_attempted"] = True
        # Use JavaScript only to move the browser to Google's hosted sign-in
        # page. The fallback button above remains available if a browser blocks
        # the automatic navigation.
        safe_url = json.dumps(auth_url)
        components.html(
            f"<script>window.top.location.replace({safe_url});</script>",
            height=0,
        )
        st.caption("Redirecting to Google sign-in…")


def authenticate() -> AppUser:
    """Require the original custom Google OAuth flow in every runtime.

    Credentials are loaded from GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and
    GOOGLE_REDIRECT_URI. Local execution reads them from .env. Streamlit Cloud
    reads the same names from top-level application secrets. There is no demo
    login, local-user fallback, email allow-list or role restriction.
    """

    settings = get_settings()
    try:
        validate_google_oauth_settings(settings)
    except ValueError as exc:
        st.error("Google authentication configuration is incomplete.")
        st.code(str(exc), language="text")
        st.info(
            "For local use, add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and "
            "GOOGLE_REDIRECT_URI to the project .env file."
        )
        st.stop()

    if "user" in st.session_state:
        return AppUser.model_validate(st.session_state.user)

    google_error = _single_query_value("error")
    code = _single_query_value("code")
    callback_state = _single_query_value("state")

    if google_error:
        error_description = _single_query_value("error_description")
        message = error_description or google_error
        st.query_params.clear()
        _clear_oauth_session()
        auth_url = _prepare_google_authorization()
        _render_google_redirect(
            auth_url,
            f"Google sign-in was not completed: {message}",
        )
        st.stop()

    if code:
        try:
            if not callback_state:
                raise ValueError("OAuth state is missing. Start sign-in again.")
            code_verifier = read_oauth_state(settings, callback_state)

            user = exchange_code_for_user(
                settings,
                code=code,
                code_verifier=code_verifier,
            )
            db_user = persist_login(user)
            st.session_state.user = db_user.model_dump(mode="json")
            st.query_params.clear()
            _clear_oauth_session()
            st.rerun()
        except Exception as exc:
            LOGGER.warning("Google sign-in failed: %s", exc)
            st.query_params.clear()
            _clear_oauth_session()
            auth_url = _prepare_google_authorization()
            _render_google_redirect(auth_url, f"Sign-in failed: {exc}")
            st.stop()

    auth_url = str(st.session_state.get("oauth_auth_url") or "")
    if not auth_url:
        auth_url = _prepare_google_authorization()
    _render_google_redirect(auth_url)
    st.stop()


def sidebar(user: AppUser) -> str:
    with st.sidebar:
        brand_wordmark()
        page = st.radio(
            "Navigation",
            ["Dashboard", "Evaluate", "History", "Glossary"],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption(user.display_name)
        st.caption(user.email)
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
    return page


def main() -> None:
    st.set_page_config(
        page_title="Enterprise AI Supervisor",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    user = authenticate()

    database = get_database()
    page = sidebar(user)
    if page == "Dashboard":
        dashboard.render(database)
    elif page == "Evaluate":
        evaluate.render(database, user)
    elif page == "History":
        history.render(database, user)
    else:
        glossary.render()


if __name__ == "__main__":
    main()
