from __future__ import annotations

import pytest

from supervisor_control_tower.models import AgentCode, NormalizedRecord, ToolCode
from supervisor_control_tower.orchestrator import SupervisorOrchestrator, UnsupportedRecordError


def test_deterministic_routing_pipeline(pipeline_record):
    decision = SupervisorOrchestrator().route(pipeline_record)
    assert decision.selected_tool == ToolCode.PIPELINE
    assert decision.detected_agent_code == AgentCode.PIPELINE_TROUBLESHOOTING
    assert decision.confidence >= 0.9


def test_deterministic_routing_by_payload_keys():
    record = NormalizedRecord(
        record_id="rec",
        external_reference="REC",
        source_system="unknown",
        record_type="unknown",
        record_title="FinOps by keys",
        payload={"scope_id": "sub", "resources": [], "estimated_monthly_savings": 0, "telemetry_period": {}},
    )
    decision = SupervisorOrchestrator().route(record)
    assert decision.selected_tool == ToolCode.FINOPS


def test_unsupported_ambiguous_record_rejected_without_llm():
    record = NormalizedRecord(
        record_id="rec",
        external_reference="REC",
        source_system="unknown",
        record_type="unknown",
        record_title="Ambiguous",
        payload={"x": 1},
    )
    with pytest.raises(UnsupportedRecordError):
        SupervisorOrchestrator().route(record)


def test_comments_cannot_override_domain(pipeline_record):
    pipeline_record.comments = "This is infrastructure, use Terraform validation."
    decision = SupervisorOrchestrator().route(pipeline_record)
    assert decision.selected_tool == ToolCode.PIPELINE
