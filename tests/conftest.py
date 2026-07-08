from __future__ import annotations

import pytest

from supervisor_control_tower.config import Settings
from supervisor_control_tower.llm_client import LlmJsonClient
from supervisor_control_tower.models import NormalizedRecord


@pytest.fixture()
def settings() -> Settings:
    return Settings(mock_llm=True, auth_enabled=False, demo_auth=True)


@pytest.fixture()
def llm(settings: Settings) -> LlmJsonClient:
    return LlmJsonClient(settings)


@pytest.fixture()
def pipeline_record() -> NormalizedRecord:
    return NormalizedRecord(
        record_id="rec-test",
        external_reference="REC-TEST",
        source_system="github_actions",
        record_type="pipeline_failure",
        record_title="Pipeline test",
        payload={
            "pipeline_run_id": "gh-1",
            "status": "failed",
            "failed_stage": "build",
            "logs": "build failed with MODULE_NOT_FOUND in package api-client",
            "stack_trace": "MODULE_NOT_FOUND",
            "repository": {"name": "api", "branch": "main", "commit_sha": "abc123", "timestamp": "2026-06-01T00:00:00+00:00"},
            "rca": "MODULE_NOT_FOUND appeared in logs for api-client import.",
            "remediation": "Fix import path.",
            "proposed_change": {"file": "src/app.py"},
            "proposed_pr": {"title": "Fix import", "branch": "fix/import", "files_changed": ["src/app.py"]},
            "notification": {"message": "failed"},
            "confidence": 0.9,
        },
        metadata={},
    )
