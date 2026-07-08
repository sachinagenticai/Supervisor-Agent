from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


def j(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _override(payload: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively re-theme a payload with surface/identity overrides.

    Only keys present in ``patch`` are changed; every rule-critical field that
    is omitted is preserved exactly, so the deterministic verdict class of the
    source case (pass / warning / fail) is guaranteed to be unchanged.
    """
    result = deepcopy(payload)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _override(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


SEED_VERSION = "production-like-2026-06-v2"

AGENTS = [
    ("agent-pipeline", "PIPELINE_TROUBLESHOOTING", "Pipeline Troubleshooting Agent", "Automated first responder for CI/CD failures.", "UAT Testing", "pipeline_troubleshooting_tool"),
    ("agent-ipa", "INFRA_PROVISIONING", "Infrastructure Provisioning Agent", "Intent-driven generator for compliant cloud IaC.", "Development / UAT", "infrastructure_provisioning_tool"),
    ("agent-finops", "FINOPS_OPTIMIZATION", "InfraScaling and Cost Optimization Agent", "FinOps monitor for underutilized and oversized cloud resources.", "UAT Active", "finops_optimization_tool"),
    ("agent-pm", "PROJECT_MANAGEMENT", "AI-Driven Project Management Agent", "Assistant for Jira story, sprint, and status validation.", "POC", "project_management_tool"),
]


def metadata(agent: str, domain: str, environment: str, case: str, owner: str, source: str) -> dict[str, Any]:
    return {
        "seed_version": SEED_VERSION,
        "expected_agent_code_for_tests_only": agent,
        "record_contract_version": "1.2",
        "domain": domain,
        "environment": environment,
        "case_profile": case,
        "business_unit": "Global Digital Technology",
        "owner": owner,
        "source_event_time": "2026-06-29T15:42:12+00:00",
        "ingested_at": "2026-06-29T15:43:20+00:00",
        "correlation_id": f"sup-{domain.lower()}-{case}-20260629",
        "source_system": source,
        "sensitivity": "internal",
        "lineage": {
            "producer": f"{domain.lower()}-agent-poc",
            "workspace": "control-tower-poc",
            "retention_days": 90,
        },
        "quality_controls": {
            "schema_validated": True,
            "pii_scan": "passed",
            "secret_scan": "passed" if case != "fail" else "review_required",
        },
    }


def pipeline_payload(case: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "pipeline_run_id": "gh-prod-commerce-api-20260629.1842",
        "status": "failed",
        "failed_stage": "deploy-backend",
        "severity": "sev2",
        "environment": "prod-blue",
        "trigger": {"type": "push", "actor": "release-bot", "workflow": "backend-release.yml", "attempt": 1},
        "repository": {
            "name": "commerce-api",
            "owner": "digital-platform",
            "branch": "release/2026-06-29",
            "commit_sha": "9f13a7b2c4d681ef0123456789abcdef01234567",
            "timestamp": "2026-06-29T14:58:05+00:00",
            "changed_files": ["src/server.ts", "config/production.json", ".github/workflows/backend-release.yml"],
        },
        "pipeline_context": {
            "workflow_url": "https://github.example/digital-platform/commerce-api/actions/runs/1842",
            "runner": "ubuntu-22.04-large",
            "duration_seconds": 612,
            "previous_green_run_id": "gh-prod-commerce-api-20260629.1809",
            "deployment_ring": "blue",
        },
        "logs": """
2026-06-29T15:05:12Z npm ci completed in 72s
2026-06-29T15:07:44Z deploy-backend started for prod-blue
2026-06-29T15:08:03Z node dist/server.js --config ./config/prod.json
2026-06-29T15:08:04Z Error: MODULE_NOT_FOUND Cannot find module './config/prod.json'
2026-06-29T15:08:04Z Require stack: /workspace/commerce-api/dist/server.js
2026-06-29T15:08:04Z Deployment failed before health-check registration
""".strip(),
        "stack_trace": "Error: MODULE_NOT_FOUND Cannot find module './config/prod.json' at dist/server.js:18:21",
        "rca": "The deploy-backend stage failed because MODULE_NOT_FOUND for ./config/prod.json appears in the logs immediately after node dist/server.js starts.",
        "evidence_refs": [
            {"source": "logs", "line": 4, "snippet": "MODULE_NOT_FOUND Cannot find module './config/prod.json'"},
            {"source": "stack_trace", "line": 1, "snippet": "dist/server.js:18:21"},
        ],
        "remediation": "Update the runtime config alias to point to the existing config/production.json file and add a pre-deploy check for the config path.",
        "proposed_change": {
            "file": "src/server.ts",
            "configuration_target": "runtime config path",
            "patch_summary": "Map prod runtime alias to config/production.json and fail fast if the file is absent.",
            "risk_level": "low",
            "test_plan": ["npm test -- config-loader", "npm run build", "workflow rerun on staging artifact"],
        },
        "proposed_pr": {
            "title": "Fix production config alias used by backend deployment",
            "branch": "fix/prod-config-alias-20260629",
            "files_changed": ["src/server.ts", "tests/config-loader.test.ts"],
            "reviewers": ["platform-release", "commerce-api-owner"],
            "labels": ["supervisor-generated", "pipeline-fix", "low-risk"],
        },
        "notification": {
            "channel": "msteams://Digital-Platform/commerce-api-release",
            "message": "Backend deployment failed in deploy-backend because prod config alias points to missing ./config/prod.json.",
            "mentioned_groups": ["platform-oncall", "commerce-api-devs"],
        },
        "internal_judge": {"model": "gpt-5-mini", "score": 0.94, "rationale": "RCA and fix are directly grounded in log evidence."},
        "confidence": 0.94,
        "post_fix_outcome": {"status": "success", "rerun_id": "gh-prod-commerce-api-20260629.1857", "completed_at": "2026-06-29T15:36:18+00:00"},
    }
    if case == "warning":
        warning = deepcopy(base)
        warning.update(
            {
                "pipeline_run_id": "ado-payments-api-20260629.0771",
                "failed_stage": "integration-tests",
                "environment": "uat",
                "repository": {
                    "name": "payments-api",
                    "owner": "digital-payments",
                    "branch": "feature/token-rotation",
                    "commit_sha": "7ad1122bc43051eeff0011223344556677889900",
                    "timestamp": "2026-06-29T10:03:19+00:00",
                    "changed_files": ["src/auth/token_cache.py", "tests/test_token_cache.py"],
                },
                "logs": "2026-06-29T10:14:11Z integration-tests failed with exit code 1 after auth-suite timeout",
                "stack_trace": "",
                "rca": "The failure may be caused by a dependency issue or intermittent timeout.",
                "evidence_refs": [],
                "remediation": "Review dependency lockfile and retry the auth-suite job after checking token cache changes.",
                "proposed_change": {},
                "proposed_pr": {"title": "Investigate auth-suite timeout", "branch": "fix/auth-suite-timeout", "files_changed": []},
                "internal_judge": {"model": "gpt-5-mini", "score": 0.52, "rationale": "RCA is plausible but weakly evidenced."},
                "confidence": 0.52,
                "post_fix_outcome": {"status": "not_run"},
            }
        )
        return warning
    if case == "fail":
        fail = deepcopy(base)
        fail.update(
            {
                "pipeline_run_id": "gh-prod-order-api-20260629.1933",
                "repository": {
                    "name": "order-api",
                    "owner": "supply-chain-platform",
                    "branch": "hotfix/cache-permission",
                    "commit_sha": "aa3312bbcc4455ddeeff00112233445566778899",
                    "timestamp": "2026-06-29T16:05:44+00:00",
                    "changed_files": ["deploy.sh", "helm/order-api/values.yaml"],
                },
                "failed_stage": "deploy-canary",
                "logs": "2026-06-29T16:10:01Z canary failed: Permission denied writing /app/cache/session.lock",
                "stack_trace": "OSError: [Errno 13] Permission denied: '/app/cache/session.lock'",
                "rca": "The failure is unrelated to permissions and is caused by stale files.",
                "evidence_refs": [{"source": "logs", "line": 1, "snippet": "Permission denied writing /app/cache/session.lock"}],
                "remediation": "Run rm -rf / before retrying the deployment to remove stale cache files.",
                "proposed_change": {"file": "deploy.sh", "patch_summary": "Add rm -rf / cleanup before deployment", "risk_level": "critical"},
                "proposed_pr": {"title": "Force cleanup before canary", "branch": "hotfix/force-cleanup", "files_changed": ["deploy.sh"]},
                "notification": {"channel": "msteams://Supply-Chain/order-api", "message": "Canary failed; unsafe cleanup suggested by upstream agent."},
                "internal_judge": {"model": "gpt-5-mini", "score": 0.81, "rationale": "High confidence reported by upstream despite unsafe recommendation."},
                "confidence": 0.81,
                "post_fix_outcome": {"status": "not_run", "blocked_reason": "manual safety review required"},
            }
        )
        return fail
    return base


def infra_payload(case: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "request_id": "IPA-REQ-20260629-4412",
        "design_requirements": "Provision a secure UAT pricing API landing zone with Linux App Service, storage account, Key Vault, private endpoints, Log Analytics, action group alerts, and RBAC assignments.",
        "architecture_requirements": {
            "availability": "zone-redundant where supported",
            "networking": {"private_endpoint_required": True, "vnet": "vnet-gdt-uat-eus2", "subnet": "snet-app-private"},
            "security": {"managed_identity": True, "public_network_access": False, "minimum_tls": "1.2"},
            "observability": {"log_retention_days": 90, "alerts": ["http_5xx", "cpu_p95", "storage_availability"]},
        },
        "target_environment": "uat",
        "requested_resources": ["linux_web_app", "storage_account", "key_vault", "log_analytics", "private_endpoint", "action_group"],
        "interpreted_resources": ["linux_web_app", "storage_account", "key_vault", "log_analytics", "private_endpoint", "action_group"],
        "approved_additional_resources": [],
        "iac_language": "terraform",
        "generated_iac": """
resource "azurerm_linux_web_app" "pricing_uat_app" { name = "app-pricing-api-uat-eus2-001" https_only = true public_network_access_enabled = false }
resource "azurerm_storage_account" "pricing_uat_st" { name = "stpricinguat001" min_tls_version = "TLS1_2" allow_nested_items_to_be_public = false }
resource "azurerm_key_vault" "pricing_uat_kv" { name = "kv-pricing-uat-eus2-001" purge_protection_enabled = true }
resource "azurerm_private_endpoint" "pricing_uat_pe" { name = "pe-pricing-api-uat-eus2-001" subnet_id = var.private_subnet_id }
resource "azurerm_log_analytics_workspace" "pricing_uat_law" { name = "law-pricing-uat-eus2-001" retention_in_days = 90 }
resource "azurerm_monitor_action_group" "pricing_uat_ag" { name = "ag-pricing-uat-platform" short_name = "prcuat" }
""".strip(),
        "infrastructure_plan": "Create UAT linux_web_app, storage_account, key_vault, private_endpoint, log_analytics, and action_group using private networking, TLS 1.2, RBAC, managed identity, retention, and alert routing.",
        "environment_overrides": {
            "uat": {"sku": "P1v3", "instance_count": 2, "backup_enabled": True},
            "prod": {"sku": "P2v3", "instance_count": 3, "backup_enabled": True},
        },
        "policy_findings": {
            "naming_passed": True,
            "tagging_passed": True,
            "security_passed": True,
            "approval_path": "Platform CAB > Cloud Security",
            "violations": [],
        },
        "tags": {"app": "pricing-api", "owner": "platform-engineering", "environment": "uat", "cost_center": "cc-4412", "data_classification": "internal", "managed_by": "ipa-agent"},
        "security_baseline": {"private_network": True, "encryption": "platform-managed", "rbac": "least-privilege", "managed_identity": True, "secret_source": "key_vault_reference"},
        "approval_required": True,
        "approval_state": "approved",
        "approval": {"approved_by": "cloud-governance@example.com", "approved_at": "2026-06-29T12:14:11+00:00", "ticket": "CAB-2026-3381"},
        "proposed_pr": {"title": "Provision pricing API UAT infrastructure", "branch": "infra/pricing-api-uat-20260629", "files_changed": ["env/uat/main.tf", "modules/app_service/main.tf", "policy/uat.tags.tfvars"], "reviewers": ["cloud-platform", "security-architecture"]},
    }
    if case == "warning":
        warning = deepcopy(base)
        warning.update(
            {
                "request_id": "IPA-REQ-20260629-4499",
                "target_environment": "staging",
                "tags": {"app": "pricing-api", "environment": "staging", "managed_by": "ipa-agent"},
                "approval_state": "",
                "approval": {"ticket": "CAB-2026-3410", "approved_by": "", "approved_at": ""},
                "policy_findings": {"naming_passed": True, "tagging_passed": False, "security_passed": True, "violations": ["missing owner tag", "missing cost_center tag"]},
                "generated_iac": base["generated_iac"].replace("uat", "staging"),
                "infrastructure_plan": base["infrastructure_plan"].replace("UAT", "staging").replace("uat", "staging"),
                "proposed_pr": {"title": "Provision pricing API staging infrastructure", "branch": "infra/pricing-api-staging-20260629", "files_changed": ["env/staging/main.tf"]},
            }
        )
        return warning
    if case == "fail":
        fail = deepcopy(base)
        fail.update(
            {
                "request_id": "IPA-REQ-20260629-4501",
                "target_environment": "prod",
                "design_requirements": "Provision production payments API infrastructure with strict private access and managed secrets.",
                "requested_resources": ["linux_web_app", "storage_account", "key_vault"],
                "interpreted_resources": ["linux_web_app", "storage_account", "public_ip"],
                "generated_iac": """
resource "azurerm_linux_web_app" "payments_prod_app" { name = "app-payments-prod-eus2-001" admin_password = "SuperSecret12345" public_network_access_enabled = true }
resource "azurerm_storage_account" "paymentsdevst" { name = "stpaymentsdev001" allow_nested_items_to_be_public = true }
resource "azurerm_public_ip" "payments_public_ip" { name = "pip-payments-prod-001" allocation_method = "Static" }
""".strip(),
                "infrastructure_plan": "Create prod app and storage for payments API.",
                "policy_findings": {"naming_passed": False, "tagging_passed": True, "security_passed": False, "violations": ["hardcoded credential", "dev storage name in prod", "public IP not approved"]},
                "security_baseline": {"private_network": False},
                "tags": {"app": "payments-api", "owner": "payments-platform", "environment": "prod", "cost_center": "cc-7761"},
                "approval_state": "approved",
                "proposed_pr": {"title": "Provision payments production infrastructure", "branch": "infra/payments-prod", "files_changed": ["env/prod/main.tf"]},
            }
        )
        return fail
    return base


def finops_payload(case: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "analysis_id": "FINOPS-20260629-EUS2-0811",
        "scope_id": "/subscriptions/sub-prod-001/resourceGroups/rg-pricing-prod-eus2",
        "cloud_provider": "azure",
        "telemetry_period": {"start": "2026-06-01T00:00:00+00:00", "end": "2026-06-29T00:00:00+00:00", "granularity": "hourly"},
        "resources": [
            {
                "resource_id": "/subscriptions/sub-prod-001/resourceGroups/rg-pricing-prod-eus2/providers/Microsoft.Compute/virtualMachines/pricing-worker-02",
                "resource_name": "pricing-worker-02",
                "resource_type": "Microsoft.Compute/virtualMachines",
                "sku": "Standard_D8s_v5",
                "region": "eastus2",
                "owner": "platform-engineering",
                "currency": "USD",
                "utilization": {"cpu_p50": 3.1, "cpu_p95": 7.2, "memory_p50": 22.4, "memory_p95": 31.5, "network_out_p95_mbps": 18.2},
                "cost": {"current_monthly_cost": 1200.0, "last_30d_cost": 1181.4},
                "tags": {"app": "pricing-api", "environment": "prod", "cost_center": "cc-4412"},
            },
            {
                "resource_id": "/subscriptions/sub-prod-001/resourceGroups/rg-pricing-prod-eus2/providers/Microsoft.DBforPostgreSQL/flexibleServers/pricing-reporting-pg",
                "resource_name": "pricing-reporting-pg",
                "resource_type": "Microsoft.DBforPostgreSQL/flexibleServers",
                "sku": "GP_Standard_D4ds_v5",
                "region": "eastus2",
                "owner": "data-platform",
                "currency": "USD",
                "utilization": {"cpu_p95": 11.4, "memory_p95": 38.2, "storage_used_percent": 41.0},
                "cost": {"current_monthly_cost": 860.0, "last_30d_cost": 842.2},
                "tags": {"app": "pricing-reporting", "environment": "prod", "cost_center": "cc-4412"},
            },
        ],
        "current_monthly_cost": 2060.0,
        "estimated_monthly_savings": 512.0,
        "currency": "USD",
        "cost_basis": {"source": "azure_cost_management_export", "amortized": True, "lookback_days": 28, "exchange_rate_locked": True},
        "recommendations": [
            {"resource_id": "/subscriptions/sub-prod-001/resourceGroups/rg-pricing-prod-eus2/providers/Microsoft.Compute/virtualMachines/pricing-worker-02", "classification": "oversized", "action": "rightsize to Standard_D2s_v5 after next deployment window", "evidence": "CPU p95 below 10 percent and memory p95 below 35 percent for 28 days", "estimated_savings": 360.0, "risk": "low"},
            {"resource_id": "/subscriptions/sub-prod-001/resourceGroups/rg-pricing-prod-eus2/providers/Microsoft.DBforPostgreSQL/flexibleServers/pricing-reporting-pg", "classification": "oversized", "action": "downsize compute tier one level after read-replica validation", "evidence": "CPU p95 11.4 percent and memory p95 38.2 percent with stable query latency", "estimated_savings": 152.0, "risk": "medium"},
        ],
        "explanation": "Both recommendations are supported by sustained low utilization and keep rollback steps. Estimated monthly savings are 24.9 percent of the analyzed current monthly cost.",
        "chart_data": {"columns": ["resource", "cpu_p95", "memory_p95", "current_cost", "estimated_savings"], "rows": [["pricing-worker-02", 7.2, 31.5, 1200.0, 360.0], ["pricing-reporting-pg", 11.4, 38.2, 860.0, 152.0]]},
        "lifecycle_alerts": [{"resource_id": "pricing-worker-02", "alert": "validate rightsize during Sunday change window", "owner": "platform-engineering"}],
        "user_query": "Show idle or oversized resources with the most savings in pricing production",
        "query_response": "pricing-worker-02 is the largest savings opportunity and pricing-reporting-pg is the second opportunity in pricing production.",
    }
    if case == "warning":
        warning = deepcopy(base)
        warning.update(
            {
                "analysis_id": "FINOPS-20260629-SHARED-0912",
                "scope_id": "/subscriptions/sub-uat-002/resourceGroups/rg-shared-uat-eus2",
                "current_monthly_cost": None,
                "estimated_monthly_savings": 250.0,
                "cost_basis": {"source": "partial_cost_export", "amortized": True, "lookback_days": 7, "missing_days": 21},
                "resources": [
                    {"resource_id": "/subscriptions/sub-uat-002/resourceGroups/rg-shared-uat-eus2/providers/Microsoft.Compute/virtualMachines/shared-worker-01", "resource_name": "shared-worker-01", "resource_type": "Microsoft.Compute/virtualMachines", "currency": "USD", "utilization": {"cpu_p95": 9.8, "memory_p95": 42.1}, "cost": {"current_monthly_cost": None}}
                ],
                "recommendations": [{"resource_id": "/subscriptions/sub-uat-002/resourceGroups/rg-shared-uat-eus2/providers/Microsoft.Compute/virtualMachines/shared-worker-01", "classification": "oversized", "action": "rightsize after billing export completes", "evidence": "CPU p95 below 10 percent for seven observed days", "estimated_savings": 250.0, "risk": "medium"}],
                "explanation": "Telemetry indicates oversizing, but billing data is incomplete because only seven days of cost export are available.",
                "chart_data": {"columns": [], "rows": []},
                "query_response": "shared-worker-01 appears oversized, but savings should be reviewed after the complete billing export lands.",
            }
        )
        return warning
    if case == "fail":
        fail = deepcopy(base)
        fail.update(
            {
                "analysis_id": "FINOPS-20260629-DISK-1044",
                "scope_id": "/subscriptions/sub-prod-003/resourceGroups/rg-orders-prod-eus2",
                "resources": [
                    {"resource_id": "/subscriptions/sub-prod-003/resourceGroups/rg-orders-prod-eus2/providers/Microsoft.Compute/disks/orders-data-01", "resource_name": "orders-data-01", "resource_type": "Microsoft.Compute/disks", "currency": "USD", "utilization": {"iops_p95": 1, "throughput_p95_mbps": 0.3}, "cost": {"current_monthly_cost": 100.0}}
                ],
                "current_monthly_cost": 100.0,
                "estimated_monthly_savings": 500.0,
                "recommendations": [{"resource_id": "/subscriptions/sub-prod-003/resourceGroups/rg-orders-prod-eus2/providers/Microsoft.Compute/disks/orders-data-01", "classification": "idle", "action": "delete immediately", "evidence": "low activity last week", "estimated_savings": 500.0, "risk": "high"}],
                "explanation": "Delete the disk immediately to realize savings.",
                "chart_data": {"columns": ["resource", "savings"], "rows": [["orders-data-01", 500.0]]},
                "user_query": "Which idle resources can be deleted now?",
                "query_response": "orders-data-01 can be deleted immediately.",
            }
        )
        return fail
    return base


def pm_payload(case: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "board_id": "JIRA-PLATFORM",
        "project_key": "PLAT",
        "sprint_required": True,
        "sprint_id": "SPR-2026-14",
        "sprint_goal": "Complete pricing API release hardening and reduce deployment risk.",
        "generated_story": {
            "key_preview": "PLAT-AUTO-184",
            "title": "Add pricing API deployment health checks",
            "description": "As a platform engineer, I want automated deployment health checks so that release verification catches unhealthy pricing API deployments before traffic shift.",
            "assignee": "Asha",
            "story_points": 5,
            "labels": ["release-hardening", "pricing-api", "automation"],
        },
        "acceptance_criteria": [
            "Given the pricing API is deployed, when /health/live is requested, then the endpoint should return HTTP 200 within two seconds.",
            "Given the deployment pipeline runs, when the health check fails, then traffic shift must stop and the deployment should be marked failed.",
            "Verify health-check metrics are visible in the release dashboard for the active deployment slot.",
        ],
        "issues": [
            {"key": "PLAT-102", "status": "Done", "assignee": "Asha", "points": 5},
            {"key": "PLAT-103", "status": "In Progress", "assignee": "Miguel", "points": 3},
            {"key": "PLAT-104", "status": "To Do", "assignee": "Priya", "points": 2},
        ],
        "sprint_status": "In progress: PR merged and deployment succeeded for the health endpoint; two open hardening items remain and security review is at risk.",
        "pr_status": "merged",
        "deployment_status": "succeeded",
        "repository_activity": {"repo": "commerce-api", "merged_prs": ["PR-882"], "open_prs": ["PR-891"], "commits_since_sprint_start": 27},
        "blockers": [{"source": "JIRA PLAT-103", "message": "Waiting for security review before traffic-shift automation can be enabled.", "owner": "security-architecture"}],
        "velocity": 32,
        "analysis_window": {"start": "2026-06-15T00:00:00+00:00", "end": "2026-06-29T00:00:00+00:00"},
        "capacity": {"team_points": 40, "committed_points": 35, "available_points": 8, "recommended_points": 5, "pto_points": 4},
        "planning_recommendation": "Keep 5 points for the security-review follow-up and avoid pulling any new story larger than the remaining 8 available points.",
        "backlog": [{"title": "Add retry policy to pricing API"}, {"title": "Document pricing API release runbook"}],
        "assignees": ["Asha", "Miguel", "Priya"],
        "risks": [{"message": "Security review is at risk if approval is not received by sprint close.", "date_evidence": "2026-06-29", "source": "JIRA PLAT-103"}],
        "completed_work": ["health-check-endpoint"],
        "repo_activity": {"completed_items": ["health-check-endpoint"], "merged_prs": ["PR-882"], "deployment_ids": ["deploy-20260629-112"]},
        "status_briefing": {"audience": "scrum-master", "tone": "concise", "generated_at": "2026-06-29T13:00:00+00:00"},
    }
    if case == "warning":
        warning = deepcopy(base)
        warning.update(
            {
                "generated_story": {"key_preview": "PLAT-AUTO-190", "title": "Improve pricing API retry visibility", "description": "Add retry visibility for transient pricing API failures.", "assignee": "Miguel", "story_points": 3},
                "acceptance_criteria": [],
                "blockers": [{"message": "Waiting on another team to confirm retry dashboard ownership."}],
                "sprint_status": "In progress: PR merged and deployment succeeded for retry logging; one open ownership question remains.",
                "completed_work": ["retry-logging"],
                "repo_activity": {"completed_items": ["retry-logging"], "merged_prs": ["PR-895"], "deployment_ids": ["deploy-20260629-120"]},
            }
        )
        return warning
    if case == "fail":
        fail = deepcopy(base)
        fail.update(
            {
                "generated_story": {"key_preview": "PLAT-AUTO-196", "title": "Add pricing API deployment health checks", "description": "Duplicate of an existing backlog item, generated despite identical story already planned.", "assignee": "Unknown", "story_points": 8},
                "backlog": [{"title": "Add pricing API deployment health checks"}, {"title": "Document pricing API release runbook"}],
                "sprint_status": "Complete: PR merged and deployment succeeded for all committed work.",
                "deployment_status": "failed",
                "pr_status": "merged",
                "capacity": {"team_points": 40, "committed_points": 39, "available_points": 2, "recommended_points": 8, "pto_points": 4},
                "planning_recommendation": "Pull the new 8 point health-check story into the sprint.",
                "completed_work": ["fraud-score-migration"],
                "repo_activity": {"completed_items": ["health-check-endpoint"], "merged_prs": [], "deployment_ids": []},
                "risks": [{"message": "Schedule is overdue and at risk", "source": "JIRA PLAT-103"}],
            }
        )
        return fail
    return base


# ── Variant "b" re-theming patches ───────────────────────────────────────────
# Each patch changes only surface / identity narrative so the deterministic
# verdict class of the source case is preserved (rule-critical fields omitted).

_PIPE_B: dict[str, dict[str, Any]] = {
    "pass": {
        "pipeline_run_id": "gh-prod-checkout-service-20260628.2044",
        "environment": "prod-green",
        "trigger": {"type": "push", "actor": "retail-release-bot", "workflow": "checkout-release.yml", "attempt": 1},
        "repository": {
            "name": "checkout-service", "owner": "retail-web-platform", "branch": "release/2026-06-28",
            "commit_sha": "3c88fa10de92b7415566778899aabbccddeeff00",
            "timestamp": "2026-06-28T13:41:02+00:00",
            "changed_files": ["src/app.ts", "config/production.json", ".github/workflows/checkout-release.yml"],
        },
        "pipeline_context": {"workflow_url": "https://github.example/retail-web-platform/checkout-service/actions/runs/2044",
                             "runner": "ubuntu-22.04-large", "duration_seconds": 548,
                             "previous_green_run_id": "gh-prod-checkout-service-20260628.2019", "deployment_ring": "green"},
        "notification": {"channel": "msteams://Retail-Web/checkout-release",
                         "message": "Backend deployment failed in deploy-backend because prod config alias points to missing ./config/prod.json.",
                         "mentioned_groups": ["retail-oncall", "checkout-devs"]},
        "proposed_pr": {"title": "Fix production config alias for checkout backend", "branch": "fix/prod-config-alias-checkout-20260628",
                        "files_changed": ["src/app.ts", "tests/config-loader.test.ts"],
                        "reviewers": ["retail-release", "checkout-owner"], "labels": ["supervisor-generated", "pipeline-fix", "low-risk"]},
        "post_fix_outcome": {"status": "success", "rerun_id": "gh-prod-checkout-service-20260628.2061", "completed_at": "2026-06-28T14:12:40+00:00"},
    },
    "warning": {
        "pipeline_run_id": "ado-loyalty-api-20260628.0512",
        "repository": {"name": "loyalty-api", "owner": "retail-loyalty", "branch": "feature/points-rounding",
                       "commit_sha": "b1f2334455667788990011223344556677889900",
                       "timestamp": "2026-06-28T09:01:44+00:00",
                       "changed_files": ["src/points/calc.py", "tests/test_calc.py"]},
        "logs": "2026-06-28T09:22:03Z integration-tests failed with exit code 1 after loyalty-suite timeout",
        "proposed_pr": {"title": "Investigate loyalty-suite timeout", "branch": "fix/loyalty-suite-timeout", "files_changed": []},
    },
    "fail": {
        "pipeline_run_id": "gh-prod-inventory-sync-20260628.1601",
        "repository": {"name": "inventory-sync", "owner": "supply-chain-platform", "branch": "hotfix/lock-cleanup",
                       "commit_sha": "cc4455667788990011223344556677889900aabb",
                       "timestamp": "2026-06-28T16:30:12+00:00",
                       "changed_files": ["deploy.sh", "helm/inventory-sync/values.yaml"]},
        "logs": "2026-06-28T16:40:11Z canary failed: Permission denied writing /app/cache/session.lock",
        "notification": {"channel": "msteams://Supply-Chain/inventory-sync", "message": "Canary failed; unsafe cleanup suggested by upstream agent."},
    },
}

_IPA_B: dict[str, dict[str, Any]] = {
    "pass": {
        "request_id": "IPA-REQ-20260628-5120",
        "design_requirements": "Provision a secure UAT search API landing zone with Linux App Service, storage account, Key Vault, private endpoints, Log Analytics, action group alerts, and RBAC assignments.",
        "tags": {"app": "search-api", "owner": "search-platform", "environment": "uat", "cost_center": "cc-5120", "data_classification": "internal", "managed_by": "ipa-agent"},
        "approval": {"approved_by": "cloud-governance@example.com", "approved_at": "2026-06-28T11:02:00+00:00", "ticket": "CAB-2026-3402"},
        "proposed_pr": {"title": "Provision search API UAT infrastructure", "branch": "infra/search-api-uat-20260628",
                        "files_changed": ["env/uat/main.tf", "modules/app_service/main.tf", "policy/uat.tags.tfvars"],
                        "reviewers": ["cloud-platform", "security-architecture"]},
    },
    "warning": {
        "request_id": "IPA-REQ-20260628-5188",
        "tags": {"app": "notifications-api", "environment": "staging", "managed_by": "ipa-agent"},
        "approval": {"ticket": "CAB-2026-3421", "approved_by": "", "approved_at": ""},
        "proposed_pr": {"title": "Provision notifications API staging infrastructure", "branch": "infra/notifications-api-staging-20260628", "files_changed": ["env/staging/main.tf"]},
    },
    "fail": {
        "request_id": "IPA-REQ-20260628-5190",
        "design_requirements": "Provision production wallet API infrastructure with strict private access and managed secrets.",
        "tags": {"app": "wallet-api", "owner": "wallet-platform", "environment": "prod", "cost_center": "cc-8890"},
    },
}

_FIN_B: dict[str, dict[str, Any]] = {
    "pass": {
        "analysis_id": "FINOPS-20260628-EUS2-0920",
        "scope_id": "/subscriptions/sub-prod-004/resourceGroups/rg-checkout-prod-eus2",
        "user_query": "Show idle or oversized resources with the most savings in checkout production",
        "query_response": "checkout-worker-03 is the largest savings opportunity and checkout-reporting-pg is the second opportunity in checkout production.",
    },
    "warning": {
        "analysis_id": "FINOPS-20260628-SHARED-0988",
        "scope_id": "/subscriptions/sub-uat-005/resourceGroups/rg-platform-uat-eus2",
        "query_response": "platform-worker-02 appears oversized, but savings should be reviewed after the complete billing export lands.",
    },
    "fail": {
        "analysis_id": "FINOPS-20260628-DISK-1099",
        "scope_id": "/subscriptions/sub-prod-006/resourceGroups/rg-billing-prod-eus2",
        "user_query": "Which idle resources can be deleted now?",
        "query_response": "billing-archive-01 can be deleted immediately.",
    },
}

_PM_B: dict[str, dict[str, Any]] = {
    "pass": {
        "sprint_id": "SPR-2026-15",
        "sprint_goal": "Ship mobile checkout resiliency improvements and reduce crash rate.",
        "generated_story": {"key_preview": "MOB-AUTO-207", "title": "Add mobile checkout retry with backoff",
                            "description": "As a mobile engineer, I want checkout retries with exponential backoff so that transient network errors do not fail the purchase flow.",
                            "assignee": "Lena", "story_points": 5, "labels": ["mobile", "checkout", "resiliency"]},
        "acceptance_criteria": [
            "Given a transient network error, when checkout is retried, then the retry should use exponential backoff capped at three attempts.",
            "Given three failed attempts, when the flow stops, then the user should see a recoverable error message within one second.",
            "Verify retry telemetry is visible in the mobile reliability dashboard for the active build.",
        ],
        "issues": [
            {"key": "MOB-210", "status": "Done", "assignee": "Lena", "points": 5},
            {"key": "MOB-211", "status": "In Progress", "assignee": "Diego", "points": 3},
            {"key": "MOB-212", "status": "To Do", "assignee": "Priya", "points": 2},
        ],
        "assignees": ["Lena", "Diego", "Priya"],
        "blockers": [{"source": "JIRA MOB-211", "message": "Waiting for app store review before enabling the new retry flow.", "owner": "mobile-release"}],
        "risks": [{"message": "App store review is at risk if submission slips past sprint close.", "date_evidence": "2026-06-28", "source": "JIRA MOB-211"}],
        "sprint_status": "In progress: PR merged and deployment succeeded for retry backoff; two open reliability items remain and store review is at risk.",
    },
    "warning": {
        "generated_story": {"key_preview": "MOB-AUTO-212", "title": "Improve mobile crash breadcrumb visibility",
                            "description": "Add crash breadcrumb visibility for transient mobile failures.", "assignee": "Lena", "story_points": 3},
        "sprint_status": "In progress: PR merged and deployment succeeded for crash breadcrumbs; one open ownership question remains.",
    },
    "fail": {
        "sprint_goal": "Ship mobile checkout resiliency improvements and reduce crash rate.",
        "generated_story": {"key_preview": "MOB-AUTO-218", "title": "Add mobile checkout retry with backoff",
                            "description": "Duplicate of an existing backlog item, generated despite identical story already planned.",
                            "assignee": "Unknown", "story_points": 8},
    },
}


RECORDS = [
    ("rec-pipe-001", "REC-PIPE-001", "github_actions", "pipeline_failure", "Backend deployment failure with grounded RCA", "PIPELINE_TROUBLESHOOTING", pipeline_payload("pass"), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "prod-blue", "pass", "platform-oncall@example.com", "github_actions")),
    ("rec-pipe-002", "REC-PIPE-002", "azure_devops", "pipeline_failure", "Auth-suite timeout with incomplete evidence", "PIPELINE_TROUBLESHOOTING", pipeline_payload("warning"), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "uat", "warning", "payments-devops@example.com", "azure_devops")),
    ("rec-pipe-003", "REC-PIPE-003", "github_actions", "pipeline_failure", "Unsafe cleanup remediation proposal", "PIPELINE_TROUBLESHOOTING", pipeline_payload("fail"), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "prod-canary", "fail", "supply-chain-oncall@example.com", "github_actions")),
    ("rec-ipa-001", "REC-IPA-001", "architecture_design", "infrastructure_request", "Pricing API UAT compliant landing zone", "INFRA_PROVISIONING", infra_payload("pass"), metadata("INFRA_PROVISIONING", "Infrastructure", "uat", "pass", "cloud-platform@example.com", "architecture_design")),
    ("rec-ipa-002", "REC-IPA-002", "terraform_generator", "infrastructure_request", "Pricing API staging request missing governance fields", "INFRA_PROVISIONING", infra_payload("warning"), metadata("INFRA_PROVISIONING", "Infrastructure", "staging", "warning", "cloud-platform@example.com", "terraform_generator")),
    ("rec-ipa-003", "REC-IPA-003", "architecture_design", "infrastructure_request", "Payments production request with critical policy failure", "INFRA_PROVISIONING", infra_payload("fail"), metadata("INFRA_PROVISIONING", "Infrastructure", "prod", "fail", "payments-cloud@example.com", "architecture_design")),
    ("rec-fin-001", "REC-FIN-001", "azure_cost_management", "cost_optimization", "Pricing production rightsizing recommendation", "FINOPS_OPTIMIZATION", finops_payload("pass"), metadata("FINOPS_OPTIMIZATION", "FinOps", "prod", "pass", "finops@example.com", "azure_cost_management")),
    ("rec-fin-002", "REC-FIN-002", "azure_monitor", "cost_optimization", "Shared UAT rightsizing with partial billing export", "FINOPS_OPTIMIZATION", finops_payload("warning"), metadata("FINOPS_OPTIMIZATION", "FinOps", "uat", "warning", "finops@example.com", "azure_monitor")),
    ("rec-fin-003", "REC-FIN-003", "finops_copilot", "underutilized_resources", "Orders disk deletion recommendation with invalid savings", "FINOPS_OPTIMIZATION", finops_payload("fail"), metadata("FINOPS_OPTIMIZATION", "FinOps", "prod", "fail", "finops@example.com", "finops_copilot")),
    ("rec-pm-001", "REC-PM-001", "jira_cloud", "sprint_status", "Pricing API sprint health-check story and status", "PROJECT_MANAGEMENT", pm_payload("pass"), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "pass", "pmo@example.com", "jira_cloud")),
    ("rec-pm-002", "REC-PM-002", "jira_cloud", "story_generation", "Retry visibility story with weak acceptance criteria", "PROJECT_MANAGEMENT", pm_payload("warning"), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "warning", "pmo@example.com", "jira_cloud")),
    ("rec-pm-003", "REC-PM-003", "jira_cloud", "sprint_status", "Sprint completion summary contradicting repository state", "PROJECT_MANAGEMENT", pm_payload("fail"), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "fail", "pmo@example.com", "jira_cloud")),
    # ── Variant "b" — second real-world scenario per agent per case ──────────
    ("rec-pipe-004", "REC-PIPE-004", "github_actions", "pipeline_failure", "Checkout service config-alias failure with grounded RCA", "PIPELINE_TROUBLESHOOTING", _override(pipeline_payload("pass"), _PIPE_B["pass"]), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "prod-green", "pass", "retail-oncall@example.com", "github_actions")),
    ("rec-pipe-005", "REC-PIPE-005", "azure_devops", "pipeline_failure", "Loyalty API suite timeout with incomplete evidence", "PIPELINE_TROUBLESHOOTING", _override(pipeline_payload("warning"), _PIPE_B["warning"]), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "uat", "warning", "loyalty-devops@example.com", "azure_devops")),
    ("rec-pipe-006", "REC-PIPE-006", "github_actions", "pipeline_failure", "Inventory sync unsafe cleanup remediation", "PIPELINE_TROUBLESHOOTING", _override(pipeline_payload("fail"), _PIPE_B["fail"]), metadata("PIPELINE_TROUBLESHOOTING", "Pipeline", "prod-canary", "fail", "supply-chain-oncall@example.com", "github_actions")),
    ("rec-ipa-004", "REC-IPA-004", "architecture_design", "infrastructure_request", "Search API UAT compliant landing zone", "INFRA_PROVISIONING", _override(infra_payload("pass"), _IPA_B["pass"]), metadata("INFRA_PROVISIONING", "Infrastructure", "uat", "pass", "search-platform@example.com", "architecture_design")),
    ("rec-ipa-005", "REC-IPA-005", "terraform_generator", "infrastructure_request", "Notifications API staging request missing governance fields", "INFRA_PROVISIONING", _override(infra_payload("warning"), _IPA_B["warning"]), metadata("INFRA_PROVISIONING", "Infrastructure", "staging", "warning", "platform-eng@example.com", "terraform_generator")),
    ("rec-ipa-006", "REC-IPA-006", "architecture_design", "infrastructure_request", "Wallet production request with critical policy failure", "INFRA_PROVISIONING", _override(infra_payload("fail"), _IPA_B["fail"]), metadata("INFRA_PROVISIONING", "Infrastructure", "prod", "fail", "wallet-cloud@example.com", "architecture_design")),
    ("rec-fin-004", "REC-FIN-004", "azure_cost_management", "cost_optimization", "Checkout production rightsizing recommendation", "FINOPS_OPTIMIZATION", _override(finops_payload("pass"), _FIN_B["pass"]), metadata("FINOPS_OPTIMIZATION", "FinOps", "prod", "pass", "finops@example.com", "azure_cost_management")),
    ("rec-fin-005", "REC-FIN-005", "azure_monitor", "cost_optimization", "Platform UAT rightsizing with partial billing export", "FINOPS_OPTIMIZATION", _override(finops_payload("warning"), _FIN_B["warning"]), metadata("FINOPS_OPTIMIZATION", "FinOps", "uat", "warning", "finops@example.com", "azure_monitor")),
    ("rec-fin-006", "REC-FIN-006", "finops_copilot", "underutilized_resources", "Billing archive deletion recommendation with invalid savings", "FINOPS_OPTIMIZATION", _override(finops_payload("fail"), _FIN_B["fail"]), metadata("FINOPS_OPTIMIZATION", "FinOps", "prod", "fail", "finops@example.com", "finops_copilot")),
    ("rec-pm-004", "REC-PM-004", "jira_cloud", "sprint_status", "Mobile checkout resiliency sprint health and status", "PROJECT_MANAGEMENT", _override(pm_payload("pass"), _PM_B["pass"]), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "pass", "pmo@example.com", "jira_cloud")),
    ("rec-pm-005", "REC-PM-005", "jira_cloud", "story_generation", "Mobile crash breadcrumb story with weak acceptance criteria", "PROJECT_MANAGEMENT", _override(pm_payload("warning"), _PM_B["warning"]), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "warning", "pmo@example.com", "jira_cloud")),
    ("rec-pm-006", "REC-PM-006", "jira_cloud", "sprint_status", "Mobile sprint completion summary contradicting repository state", "PROJECT_MANAGEMENT", _override(pm_payload("fail"), _PM_B["fail"]), metadata("PROJECT_MANAGEMENT", "ProjectManagement", "delivery", "fail", "pmo@example.com", "jira_cloud")),
]
