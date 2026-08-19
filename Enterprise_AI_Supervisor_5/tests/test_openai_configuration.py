from __future__ import annotations

import pytest
from pydantic import ValidationError

from supervisor_control_tower.config import Settings
from supervisor_control_tower.llm_client import LlmJsonClient


def test_openai_key_is_required_when_mock_mode_is_disabled() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(mock_llm=False, openai_api_key=None)


def test_mock_mode_does_not_require_openai_key() -> None:
    settings = Settings(mock_llm=True, openai_api_key=None)
    client = LlmJsonClient(settings)
    assert client.backend == "mock"


def test_settings_expose_no_azure_llm_fields() -> None:
    fields = set(Settings.model_fields)
    assert not any(name.startswith("azure_") for name in fields)
