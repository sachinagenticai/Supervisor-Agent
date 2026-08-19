from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from supervisor_control_tower.auth import (
    build_google_auth_url,
    create_oauth_state,
    new_pkce_pair,
    read_oauth_state,
    validate_google_oauth_settings,
)
from supervisor_control_tower.config import Settings
from supervisor_control_tower.data_science.scorecard import AssuranceScorecard
from supervisor_control_tower.models import RuleResultModel, Severity


def test_custom_google_oauth_settings_are_loaded_from_environment_fields():
    settings = Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_redirect_uri="http://localhost:8501",
    )
    validate_google_oauth_settings(settings)
    assert settings.google_client_id == "client-id"
    assert settings.google_redirect_uri == "http://localhost:8501"


def test_custom_google_oauth_requires_client_credentials():
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
        validate_google_oauth_settings(
            Settings(
                google_client_id=None,
                google_client_secret=None,
                google_redirect_uri="http://localhost:8501",
            )
        )


def test_google_authorization_url_uses_original_root_callback_and_security_values():
    settings = Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_redirect_uri="http://localhost:8501",
    )
    verifier, challenge = new_pkce_pair()
    state = create_oauth_state(settings, verifier)
    url = build_google_auth_url(
        settings,
        state=state,
        code_challenge=challenge,
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://localhost:8501"]
    assert query["state"] == [state]
    assert query["code_challenge"] == [challenge]
    assert query["code_challenge_method"] == ["S256"]
    assert len(verifier) > 40



def test_oauth_state_survives_browser_reload_and_rejects_tampering():
    settings = Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_redirect_uri="http://localhost:8501",
    )
    verifier, _ = new_pkce_pair()
    state = create_oauth_state(settings, verifier)
    assert read_oauth_state(settings, state) == verifier

    replacement = "A" if state[-1] != "A" else "B"
    with pytest.raises(ValueError, match="invalid or expired"):
        read_oauth_state(settings, state[:-1] + replacement)

def test_authentication_has_no_demo_or_email_role_settings():
    assert "demo_auth" not in Settings.model_fields
    assert "admin_emails" not in Settings.model_fields
    assert "reviewer_emails" not in Settings.model_fields
    assert "default_user_role" not in Settings.model_fields


def test_critical_failure_caps_assurance_score():
    rules = [
        RuleResultModel(
            rule_code="A",
            rule_name="Critical",
            severity=Severity.CRITICAL,
            passed=False,
            mandatory=True,
            evidence={},
            message="failed",
            tag="SAFETY",
        ),
        RuleResultModel(
            rule_code="B",
            rule_name="Other",
            severity=Severity.HIGH,
            passed=True,
            mandatory=True,
            evidence={},
            message="passed",
            tag="QUALITY",
        ),
    ]
    result = AssuranceScorecard().calculate(
        rules,
        llm_confidence=0.99,
        quality_dimensions={"safety": 0.99, "completeness": 0.99},
        data_completeness=0.99,
        routing_confidence=0.99,
    )
    assert result.final_confidence <= 0.40


def test_external_writeback_is_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(external_writeback_enabled=True)
