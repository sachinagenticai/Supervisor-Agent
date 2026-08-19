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


def test_configuration_only_document_agent_routes_without_orchestrator_code():
    record = NormalizedRecord(
        record_id="doc",
        external_reference="REC-DOC-TEST",
        source_system="sharepoint",
        record_type="policy_summary",
        record_title="Policy review",
        payload={
            "document_id": "DOC-1",
            "document_title": "Information Security Standard",
            "document_type": "policy_standard",
            "document_version": "1.0",
            "owner": {"email": "owner@example.com"},
            "approval_state": "approved",
            "approvals": [{"role": "owner", "status": "approved"}],
            "summary": "A sufficiently detailed policy summary for evaluation.",
            "content_sections": [{"section_id": "1", "text": "Mandatory control text"}],
            "extracted_requirements": [{"requirement_id": "R-1", "statement": "Control", "mandatory": True}],
            "citations": [{"claim": "Control", "section_id": "1", "page": 1}],
        },
    )
    decision = SupervisorOrchestrator().route(record)
    assert decision.detected_agent_code == "ENTERPRISE_DOCUMENT_REVIEW"
    assert decision.selected_tool == "generic_document_review_tool"
    assert decision.routing_method == "configuration"
