from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Streamlit application and services."""

    # Storage: this release is intentionally Excel-first and single-instance.
    storage_backend: str = "excel"
    excel_store_path: str = "data/supervisor_control_tower.xlsx"
    excel_lock_timeout_seconds: int = Field(default=30, ge=1, le=300)
    allow_data_reset: bool = False

    # Configuration-driven platform
    agent_config_path: str = "config/agents.json"
    rule_config_path: str = "config/rule_packs.json"
    business_context_path: str = "config/business_context.json"
    max_payload_characters: int = Field(default=120_000, ge=5_000, le=1_000_000)
    memory_reference_limit: int = Field(default=5, ge=0, le=20)

    # Standard OpenAI API only. No Azure OpenAI backend is supported.
    mock_llm: bool = True
    openai_api_key: str | None = None
    llm_model: str = "gpt-5-mini"
    llm_timeout_seconds: int = Field(default=30, ge=1, le=180)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # Custom Google OAuth, preserved from the original Supervisor Agent.
    # Local development reads these values from .env. Streamlit Community
    # Cloud can provide the same top-level names through its Secrets dashboard.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8501"
    google_oauth_timeout_seconds: int = Field(default=20, ge=5, le=60)

    # Governance and remediation. External write-back is deliberately disabled
    # in the Excel-first release; the platform produces approval-ready actions.
    remediation_proposals_enabled: bool = True
    external_writeback_enabled: bool = False
    require_human_approval_for_warning: bool = True
    degraded_mode_score_cap: float = Field(default=0.70, ge=0.0, le=1.0)
    critical_failure_score_cap: float = Field(default=0.40, ge=0.0, le=1.0)
    disagreement_penalty: float = Field(default=0.15, ge=0.0, le=0.5)

    # App
    app_env: str = "POC"
    log_level: str = "INFO"
    high_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    minimum_confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "excel":
            raise ValueError("This release supports STORAGE_BACKEND=excel only")
        return normalized

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM_MODEL cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        production = self.app_env.strip().upper() in {"PROD", "PRODUCTION"}

        if self.external_writeback_enabled:
            raise ValueError(
                "EXTERNAL_WRITEBACK_ENABLED is not supported in the Excel-first release. "
                "Remediation remains approval-only."
            )

        if not self.mock_llm and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when MOCK_LLM=false")

        if production:
            if self.mock_llm:
                raise ValueError("MOCK_LLM must be false in production.")

        return self

    def resolve_path(self, configured_path: str) -> Path:
        path = Path(configured_path)
        if path.is_absolute():
            return path
        return Path.cwd() / path





def _coerce_secret_to_env_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_streamlit_secret(secrets: Any, *keys: str) -> Any | None:
    for key in keys:
        try:
            if key in secrets:
                return secrets[key]
        except Exception:
            continue
    return None


def _load_streamlit_secrets_into_environment() -> None:
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
