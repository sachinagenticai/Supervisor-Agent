from __future__ import annotations

import re

from supervisor_control_tower.models import AgentCode, NormalizedRecord, Severity, ToolCode
from supervisor_control_tower.rules.engine import Rule, exists, field_exists, flatten_text, get, no_secret_exposure
from supervisor_control_tower.tools.base import ToolNode

VALID_ENVS = {"dev", "test", "uat", "staging", "prod", "production"}
REQUIRED_TAGS = {"app", "owner", "environment", "cost_center"}


def _target_env_valid(record: NormalizedRecord):
    env = str(get(record, "target_environment", "")).lower()
    ok = env in VALID_ENVS
    return ok, {"target_environment": env, "valid_values": sorted(VALID_ENVS)}, "Target environment is valid."


def _resources_interpreted(record: NormalizedRecord):
    required = get(record, "requested_resources", [])
    interpreted = get(record, "interpreted_resources", [])
    ok = isinstance(required, list) and isinstance(interpreted, list) and set(required).issubset(set(interpreted)) and len(required) > 0
    return ok, {"requested": required, "interpreted": interpreted}, "Required resource types were interpreted."


def _iac_exists(record: NormalizedRecord):
    iac = get(record, "generated_iac")
    return exists(iac), {"iac_present": exists(iac)}, "Generated infrastructure-as-code exists."


def _iac_language(record: NormalizedRecord):
    language = str(get(record, "iac_language", "")).lower()
    ok = language in {"terraform", "bicep"}
    return ok, {"iac_language": language}, "IaC language is identified."


def _naming_passes(record: NormalizedRecord):
    findings = get(record, "policy_findings", {})
    ok = bool(findings.get("naming_passed")) if isinstance(findings, dict) else False
    return ok, {"naming_passed": ok}, "Naming conventions pass."


def _required_tags(record: NormalizedRecord):
    tags = get(record, "tags", {})
    present = set(tags.keys()) if isinstance(tags, dict) else set()
    missing = sorted(REQUIRED_TAGS - present)
    return not missing, {"missing_tags": missing}, "Required tags exist."


def _env_not_mixed(record: NormalizedRecord):
    env = str(get(record, "target_environment", "")).lower()
    text = flatten_text(get(record, "generated_iac", "")).lower()
    other_envs = [e for e in VALID_ENVS if e not in {env, "production" if env == "prod" else "prod"}]
    found = [e for e in other_envs if re.search(rf"\b{re.escape(e)}\b", text)]
    return not found, {"target_environment": env, "other_envs_found": found}, "Environment values are not mixed."


def _security_baseline(record: NormalizedRecord):
    security = get(record, "security_baseline", {})
    required = ["private_network", "encryption", "rbac"]
    missing = [k for k in required if not exists(security.get(k))] if isinstance(security, dict) else required
    return not missing, {"missing_security_fields": missing}, "Security baseline fields exist."


def _approval_state(record: NormalizedRecord):
    required = bool(get(record, "approval_required", True))
    state = get(record, "approval_state")
    ok = exists(state) if required else True
    return ok, {"approval_required": required, "approval_state": state}, "Approval state exists when required."


def _plan_iac_consistent(record: NormalizedRecord):
    plan = flatten_text(get(record, "infrastructure_plan", "")).lower()
    iac = flatten_text(get(record, "generated_iac", "")).lower()
    resources = get(record, "interpreted_resources", [])
    matches = [r for r in resources if str(r).lower().replace("_", "") in iac.replace("_", "") or str(r).lower() in plan]
    ok = len(resources) > 0 and len(matches) >= max(1, len(resources) // 2)
    return ok, {"matched_resources": matches}, "Plan and generated IaC are consistent."


def _required_not_omitted(record: NormalizedRecord):
    required = set(get(record, "requested_resources", []) or [])
    generated = set(get(record, "interpreted_resources", []) or [])
    missing = sorted(required - generated)
    return not missing and bool(required), {"missing_resources": missing}, "Required resources are not omitted."


def _unsupported_not_added(record: NormalizedRecord):
    required = set(get(record, "requested_resources", []) or [])
    generated = set(get(record, "interpreted_resources", []) or [])
    additions = sorted(generated - required)
    approved = set(get(record, "approved_additional_resources", []) or [])
    unapproved = [a for a in additions if a not in approved]
    return not unapproved, {"unapproved_additions": unapproved}, "Unsupported resources are not added."


def _pr_valid(record: NormalizedRecord):
    pr = get(record, "proposed_pr")
    if not pr:
        return True, {"present": False}, "PR metadata is not present and is not required."
    ok = all(exists(pr.get(k)) for k in ["title", "branch", "files_changed"])
    return ok, {"present": True, "keys": sorted(pr.keys())}, "PR metadata is valid."


def build_infrastructure_rules() -> list[Rule]:
    t = ToolCode.INFRA
    return [
        Rule("IPA-001", "Design requirements exist", "Design content is mandatory.", Severity.CRITICAL, t, field_exists("design_requirements"), "Design requirements are missing.", "DESIGN_COMPLETENESS"),
        Rule("IPA-002", "Target environment valid", "Environment must be valid.", Severity.CRITICAL, t, _target_env_valid, "Target environment is missing or invalid.", "ENVIRONMENT_MAPPING"),
        Rule("IPA-003", "Resource types interpreted", "Required resources must be mapped.", Severity.HIGH, t, _resources_interpreted, "Required resource types were not interpreted.", "RESOURCE_MAPPING"),
        Rule("IPA-004", "Generated IaC exists", "Generated IaC is mandatory.", Severity.CRITICAL, t, _iac_exists, "Generated IaC is missing.", "IAC_QUALITY"),
        Rule("IPA-005", "IaC language identified", "IaC language must be Terraform or Bicep.", Severity.HIGH, t, _iac_language, "IaC language is missing or unsupported.", "IAC_QUALITY"),
        Rule("IPA-006", "Naming conventions pass", "Naming policy must pass.", Severity.HIGH, t, _naming_passes, "Naming conventions failed.", "NAMING_POLICY"),
        Rule("IPA-007", "Required tags exist", "Required corporate tags must exist.", Severity.HIGH, t, _required_tags, "Required tags are missing.", "TAGGING_POLICY"),
        Rule("IPA-008", "Environment values not mixed", "Generated IaC should not mix env values.", Severity.HIGH, t, _env_not_mixed, "Environment values are mixed.", "ENVIRONMENT_MAPPING"),
        Rule("IPA-009", "Security baseline exists", "Security baseline fields are mandatory.", Severity.CRITICAL, t, _security_baseline, "Security baseline fields are missing.", "SECURITY_BASELINE"),
        Rule("IPA-010", "No hardcoded credentials", "IaC must not include hardcoded credentials.", Severity.CRITICAL, t, no_secret_exposure, "Potential hardcoded credential detected.", "SECURITY_BASELINE"),
        Rule("IPA-011", "Approval state exists", "Human approval state is required when applicable.", Severity.MEDIUM, t, _approval_state, "Approval state is missing.", "HUMAN_APPROVAL"),
        Rule("IPA-012", "Plan matches IaC", "Plan and IaC should be consistent.", Severity.HIGH, t, _plan_iac_consistent, "Plan and generated IaC are inconsistent.", "IAC_QUALITY"),
        Rule("IPA-013", "Required resources not omitted", "All requested resources should be included.", Severity.HIGH, t, _required_not_omitted, "Required resources are omitted.", "RESOURCE_MAPPING"),
        Rule("IPA-014", "Unsupported resources not added", "Unapproved resources should not be added.", Severity.MEDIUM, t, _unsupported_not_added, "Unsupported or unapproved resources were added.", "RESOURCE_MAPPING"),
        Rule("IPA-015", "PR metadata valid", "Optional PR metadata must be valid.", Severity.MEDIUM, t, _pr_valid, "PR metadata is invalid.", "PR_STRUCTURE"),
    ]


class InfrastructureProvisioningTool(ToolNode):
    tool_code = ToolCode.INFRA
    agent_code = AgentCode.INFRA_PROVISIONING
    summary = "Infrastructure request, generated IaC, policies, and approval state were validated."

    def __init__(self) -> None:
        super().__init__(build_infrastructure_rules())
