from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration.

    Loading priority:
      1. Real environment variables
      2. Streamlit Community Cloud secrets / local .streamlit/secrets.toml
      3. Local .env file
      4. Defaults below

    For Streamlit Community Cloud, paste the TOML secrets in the app dashboard.
    For local development, either use .env or .streamlit/secrets.toml.
    """

    # ── Storage ──────────────────────────────────────────────────────────────
    storage_backend: str = "excel"
    excel_store_path: str = "data/supervisor_control_tower.xlsx"
    database_url: str = "postgresql+psycopg2://supervisor:supervisor@localhost:5432/supervisor_control_tower"

    # ── LLM / OpenAI ─────────────────────────────────────────────────────────
    mock_llm: bool = True
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_model: str = "gpt-5-mini"
    llm_timeout_seconds: int = Field(default=30, ge=1, le=120)

    # ── Authentication ───────────────────────────────────────────────────────
    auth_enabled: bool = True
    demo_auth: bool = True
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8501"

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "POC"
    log_level: str = "INFO"
    high_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
    minimum_confidence_threshold: float = Field(default=0.60, ge=0, le=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


def _coerce_secret_to_env_value(value: Any) -> str:
    """Convert TOML/Python values into environment-variable-safe strings."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_streamlit_secret(secrets: Any, *keys: str) -> Any | None:
    """Safely read a key from st.secrets without failing outside Streamlit Cloud."""
    for key in keys:
        try:
            if key in secrets:
                return secrets[key]
        except Exception:
            continue
    return None


def _load_streamlit_secrets_into_environment() -> None:
    """Load Streamlit secrets into os.environ before Pydantic reads settings.

    Streamlit Cloud stores secrets in st.secrets instead of a local .env file.
    This bridge lets the rest of the application continue using Settings without
    changing all modules individually.
    """
    try:
        import streamlit as st  # type: ignore
    except Exception:
        return

    try:
        secrets = st.secrets
    except Exception:
        return

    for field_name in Settings.model_fields:
        env_name = field_name.upper()

        # Do not override real environment variables.
        if os.getenv(env_name) is not None:
            continue

        value = _read_streamlit_secret(secrets, env_name, field_name)
        if value is not None:
            os.environ[env_name] = _coerce_secret_to_env_value(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_streamlit_secrets_into_environment()
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()