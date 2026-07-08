from __future__ import annotations

from supervisor_control_tower.models import NormalizedRecord, Severity, ToolCode
from supervisor_control_tower.tools.finops import FinOpsOptimizationTool
from supervisor_control_tower.tools.infrastructure import InfrastructureProvisioningTool
from supervisor_control_tower.tools.pipeline import PipelineTroubleshootingTool
from supervisor_control_tower.tools.project_management import ProjectManagementTool


def test_pipeline_detects_unsafe_command(pipeline_record):
    pipeline_record.payload["remediation"] = "Run rm -rf / to clean the deployment image."
    result = PipelineTroubleshootingTool().run(pipeline_record)
    failed = [r for r in result.rule_results if not r.passed]
    assert any(r.rule_code == "PIPE-011" and r.severity == Severity.CRITICAL for r in failed)


def test_infrastructure_detects_hardcoded_secret():
    record = NormalizedRecord(
        record_id="r", external_reference="R", source_system="architecture_design", record_type="infrastructure_request", record_title="Infra",
        payload={
            "design_requirements": "web app", "target_environment": "prod", "requested_resources": ["app_service"], "interpreted_resources": ["app_service"],
            "generated_iac": "resource app { admin_password = 'SuperSecret12345' }", "iac_language": "terraform",
            "policy_findings": {"naming_passed": True}, "tags": {"app": "a", "owner": "o", "environment": "prod", "cost_center": "c"},
            "security_baseline": {"private_network": True, "encryption": True, "rbac": True}, "approval_state": "approved", "infrastructure_plan": "app_service",
        },
    )
    result = InfrastructureProvisioningTool().run(record)
    assert any(not r.passed and r.rule_code == "IPA-010" for r in result.rule_results)


def test_finops_detects_savings_above_cost():
    record = NormalizedRecord(
        record_id="r", external_reference="R", source_system="azure_cost_management", record_type="cost_optimization", record_title="FinOps",
        payload={
            "scope_id": "sub", "resources": [{"resource_id": "vm1", "resource_type": "vm", "currency": "USD", "utilization": {"cpu": 2}}],
            "telemetry_period": {"start": "2026-06-01T00:00:00+00:00", "end": "2026-06-02T00:00:00+00:00"},
            "current_monthly_cost": 100, "estimated_monthly_savings": 200, "currency": "USD",
            "recommendations": [{"resource_id": "vm1", "classification": "oversized", "action": "rightsize", "evidence": "CPU low"}], "explanation": "low CPU",
        },
    )
    result = FinOpsOptimizationTool().run(record)
    assert any(not r.passed and r.rule_code == "FIN-009" for r in result.rule_results)


def test_project_detects_fabricated_completed_work():
    record = NormalizedRecord(
        record_id="r", external_reference="R", source_system="jira_cloud", record_type="sprint_status", record_title="PM",
        payload={
            "board_id": "B", "sprint_id": "S", "sprint_goal": "goal", "generated_story": {"title": "T", "description": "D", "assignee": "A"},
            "acceptance_criteria": ["Given X when Y then Z should pass"], "issues": [{"status": "Done"}], "sprint_status": "complete pr merged deployment succeeded",
            "pr_status": "merged", "deployment_status": "succeeded", "velocity": 1,
            "analysis_window": {"start": "2026-06-01T00:00:00+00:00", "end": "2026-06-02T00:00:00+00:00"},
            "capacity": {"available_points": 5, "recommended_points": 3}, "planning_recommendation": "take 3 points", "backlog": [], "assignees": ["A"],
            "completed_work": ["not-in-repo"], "repo_activity": {"completed_items": []},
        },
    )
    result = ProjectManagementTool().run(record)
    assert any(not r.passed and r.rule_code == "PM-015" for r in result.rule_results)
