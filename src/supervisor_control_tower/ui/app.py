from __future__ import annotations

import logging
import os
from pathlib import Path

import streamlit as st

from supervisor_control_tower.auth import build_google_auth_url, demo_user, exchange_code_for_user
from supervisor_control_tower.config import get_settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AppUser
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import inject_css, brand_wordmark, TOKENS
from supervisor_control_tower.ui.pages import glossary, overview, review_history, run_validation
from supervisor_control_tower.ui.pages import insights_page, agent_status

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

_PAGES = [
    ("Overview", "Overview"),
    ("Run Validation", "Run Validation"),
    ("Agent Status", "Agent Status"),
    ("Insights & Drift", "Insights & Drift"),
    ("Review History", "Review History"),
    ("Glossary", "Glossary"),
]


def get_database() -> Database:
    if "database" not in st.session_state:
        st.session_state.database = Database(get_settings())
    return st.session_state.database


def persist_login(user: AppUser) -> AppUser:
    db = get_database()
    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        db_user = repo.upsert_user(user)
        repo.add_audit_event(None, db_user.id, "sign_in", {"email": db_user.email})
        return db_user


# def authenticate() -> AppUser | None:
#     settings = get_settings()

#     # Auth disabled — auto-login as demo user
#     if not settings.auth_enabled:
#         user = demo_user()
#         st.session_state.user = persist_login(user).model_dump()
#         return AppUser(**st.session_state.user)

#     # Already logged in
#     if "user" in st.session_state:
#         return AppUser(**st.session_state.user)

#     # ── Handle Google OAuth callback ──────────────────────────────────────
#     # Google redirects back with ?code=... appended to GOOGLE_REDIRECT_URI.
#     # st.query_params.clear() triggers its own rerun so we MUST NOT call
#     # st.rerun() afterwards — it would create a double-rerun race.
#     # Instead: store the user in session_state FIRST, then clear params.
#     # On the next render cycle (triggered by clear), session_state.user
#     # exists and the user is admitted.
#     code = st.query_params.get("code")
#     google_error = st.query_params.get("error")

#     if google_error:
#         st.session_state["auth_error"] = f"Google returned an error: {google_error}"
#         st.query_params.clear()

#     elif code:
#         try:
#             user = exchange_code_for_user(settings, code)
#             db_user = persist_login(user)
#             st.session_state.user = db_user.model_dump()
#             st.session_state.pop("auth_error", None)
#             # Clear params AFTER storing user — this triggers the rerun that
#             # checks session_state.user at the top of this function.
#             st.query_params.clear()
#         except Exception as exc:
#             st.session_state["auth_error"] = f"Sign-in failed: {exc}"
#             st.query_params.clear()
#         return None   # wait for rerun triggered by clear()

#     # ── Render login page ─────────────────────────────────────────────
#     _render_login_page()

#     if "auth_error" in st.session_state:
#         st.error(st.session_state["auth_error"])

#     # Demo User is the primary CTA — always shown first
#     if st.button("Enter as Demo User", type="primary", use_container_width=True):
#         user = persist_login(demo_user())
#         st.session_state.user = user.model_dump()
#         st.rerun()

#     # Google sign-in as a secondary option (only if credentials are configured)
#     if settings.google_client_id and settings.google_client_secret:
#         st.markdown(
#             "<div style='text-align:center;padding:10px 0 4px;color:#98a1ad;font-size:13px;'>— or —</div>",
#             unsafe_allow_html=True,
#         )
#         auth_url = build_google_auth_url(settings)
#         st.link_button("Sign in with Google", auth_url, use_container_width=True)

#     return None

def authenticate() -> AppUser | None:
    settings = get_settings()

    # Auth disabled — auto-login as demo user
    if not settings.auth_enabled:
        user = demo_user()
        st.session_state.user = persist_login(user).model_dump()
        return AppUser(**st.session_state.user)

    # Already logged in
    if "user" in st.session_state:
        return AppUser(**st.session_state.user)

    # Handle Google OAuth callback
    code = st.query_params.get("code")
    google_error = st.query_params.get("error")

    if google_error:
        st.session_state["auth_error"] = f"Google returned an error: {google_error}"
        st.query_params.clear()
        st.rerun()

    if code:
        try:
            user = exchange_code_for_user(settings, code)
            db_user = persist_login(user)

            st.session_state.user = db_user.model_dump()
            st.session_state.pop("auth_error", None)

            st.query_params.clear()
            st.rerun()

        except Exception as exc:
            st.session_state["auth_error"] = f"Sign-in failed: {exc}"
            st.query_params.clear()
            st.rerun()

    # Render login page
    _render_login_page()

    if "auth_error" in st.session_state:
        st.error(st.session_state["auth_error"])

    # Demo login only if enabled
    if settings.demo_auth:
        if st.button("Enter as Demo User", type="primary", use_container_width=True, key="demo_login_button"):
            user = persist_login(demo_user())
            st.session_state.user = user.model_dump()
            st.rerun()

    # Google sign-in
    if settings.google_client_id and settings.google_client_secret:
        if settings.demo_auth:
            st.markdown(
                "<div style='text-align:center;padding:10px 0 4px;color:#98a1ad;font-size:13px;'>— or —</div>",
                unsafe_allow_html=True,
            )

        auth_url = build_google_auth_url(settings)
        st.link_button(
            "Sign in with Google",
            auth_url,
            use_container_width=True,
        )

    return None

def _render_login_page() -> None:
    t = TOKENS
    st.markdown(
        f"""
        <div style="text-align:center; padding: 64px 0 28px 0;">
          <div style="width:56px; height:56px; border-radius:14px; margin:0 auto 20px;
                      background:linear-gradient(135deg,{t['accent']},{t['accent_hover']});
                      display:flex; align-items:center; justify-content:center;">
            <div style="width:22px; height:22px; border:3px solid #fff; border-radius:6px;"></div>
          </div>
          <h1 style="font-size:30px; font-weight:800; color:{t['text']}; margin-bottom:10px; letter-spacing:-0.02em;">
            Supervisor Agent
          </h1>
          <p style="color:{t['text_muted']}; font-size:15.5px; max-width:540px; margin:0 auto 8px; line-height:1.6;">
            A single control plane to orchestrate, supervise, and validate your AI agents —
            with rule-based governance, LLM-as-a-Judge review, drift detection, and
            production-readiness scoring.
          </p>
          <div style="display:flex; gap:8px; justify-content:center; margin:18px 0 30px; flex-wrap:wrap;">
            <span style="font-size:12px; color:{t['text_muted']}; background:{t['surface']};
                         border:1px solid {t['border']}; border-radius:999px; padding:5px 13px;">Rule governance</span>
            <span style="font-size:12px; color:{t['text_muted']}; background:{t['surface']};
                         border:1px solid {t['border']}; border-radius:999px; padding:5px 13px;">LLM-as-a-Judge</span>
            <span style="font-size:12px; color:{t['text_muted']}; background:{t['surface']};
                         border:1px solid {t['border']}; border-radius:999px; padding:5px 13px;">Drift detection</span>
            <span style="font-size:12px; color:{t['text_muted']}; background:{t['surface']};
                         border:1px solid {t['border']}; border-radius:999px; padding:5px 13px;">Readiness scoring</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar(user: AppUser) -> str:
    settings = get_settings()

    # LLM backend label for sidebar
    if settings.mock_llm:
        llm_label = f"{settings.llm_model} · mock"
        llm_color = TOKENS["warn"]
        llm_bg = TOKENS["warn_soft"]
    else:
        llm_label = f"{settings.llm_model} · OpenAI"
        llm_color = TOKENS["pass"]
        llm_bg = TOKENS["pass_soft"]

    with st.sidebar:
        brand_wordmark()
        st.divider()
        labels = [label for label, _ in _PAGES]
        keys = [key for _, key in _PAGES]
        selected_idx = st.radio(
            "nav",
            range(len(labels)),
            format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
        page = keys[selected_idx]
        st.divider()
        st.markdown(
            f"""
            <div style="padding:0 2px;">
              <div style="font-size:11px; color:{TOKENS['text_subtle']}; text-transform:uppercase;
                          letter-spacing:.05em; font-weight:600;">Environment</div>
              <div style="font-size:13px; color:{TOKENS['text']}; font-weight:600; margin-bottom:12px;">{settings.app_env}</div>
              <div style="font-size:11px; color:{TOKENS['text_subtle']}; text-transform:uppercase;
                          letter-spacing:.05em; font-weight:600;">LLM backend</div>
              <div style="display:inline-block; margin:3px 0 14px; font-size:12px; font-weight:600;
                          color:{llm_color}; background:{llm_bg}; border-radius:7px; padding:3px 10px;">{llm_label}</div>
              <div style="font-size:11px; color:{TOKENS['text_subtle']}; text-transform:uppercase;
                          letter-spacing:.05em; font-weight:600;">Signed in</div>
              <div style="font-size:13px; color:{TOKENS['text']}; font-weight:500;">{user.display_name}</div>
              <div style="font-size:11.5px; color:{TOKENS['text_subtle']};">{user.email}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        if st.button("Sign out", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()
    return page


def main() -> None:
    st.set_page_config(
        page_title="Supervisor Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    user = authenticate()
    if not user:
        return
    db = get_database()
    page = sidebar(user)
    if page == "Overview":
        overview.render(db)
    elif page == "Run Validation":
        run_validation.render(db, user)
    elif page == "Agent Status":
        agent_status.render(db)
    elif page == "Insights & Drift":
        insights_page.render(db)
    elif page == "Review History":
        review_history.render(db)
    else:
        glossary.render()


if __name__ == "__main__":
    main()
