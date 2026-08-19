from __future__ import annotations

from supervisor_control_tower.models import AgentCode, NormalizedRecord, Severity, ToolCode
from supervisor_control_tower.rules.engine import Rule, confidence_in_range, exists, field_exists, flatten_text, get, no_secret_exposure, no_unsafe_shell_command
from supervisor_control_tower.tools.base import ToolNode


def _supported_source(record: NormalizedRecord):
    supported = {"github_actions", "azure_devops", "jenkins"}
    ok = record.source_system in supported
    return ok, {"source_system": record.source_system, "supported": sorted(supported)}, "Source system is supported for pipeline troubleshooting."


def _logs_or_stack(record: NormalizedRecord):
    logs = get(record, "logs") or get(record, "stack_trace")
    return exists(logs), {"has_logs_or_stack_trace": exists(logs)}, "Logs or stack trace are available."


def _rca_references_logs(record: NormalizedRecord):
    rca = str(get(record, "rca", ""))
    logs = flatten_text(get(record, "logs") or get(record, "stack_trace"))
    tokens = [t for t in rca.replace("_", " ").split() if len(t) > 5]
    matches = [t for t in tokens if t.lower() in logs.lower()]
    ok = bool(rca.strip()) and len(matches) >= 1
    return ok, {"matches": matches[:5]}, "RCA references evidence found in logs."


def _proposed_change_target(record: NormalizedRecord):
    change = get(record, "proposed_change", {})
    target = change.get("file") or change.get("configuration_target") if isinstance(change, dict) else None
    remediation = get(record, "remediation")
    ok = not exists(remediation) or exists(target)
    return ok, {"target": target}, "Proposed change identifies a relevant file or configuration target."


def _pr_valid(record: NormalizedRecord):
    pr = get(record, "proposed_pr")
    if not pr:
        return True, {"present": False}, "PR metadata is not present and is not required."
    ok = all(exists(pr.get(k)) for k in ["title", "branch", "files_changed"])
    return ok, {"present": True, "keys": sorted(pr.keys())}, "PR metadata is structurally valid."


def _rerun_consistent(record: NormalizedRecord):
    outcome = get(record, "post_fix_outcome")
    if not outcome:
        return True, {"present": False}, "Post-fix outcome is not present and is not required."
    status = str(outcome.get("status", "")).lower() if isinstance(outcome, dict) else ""
    ok = status in {"success", "passed", "failed", "not_run"}
    return ok, {"status": status}, "Post-fix outcome is internally consistent."


def _repo_context(record: NormalizedRecord):
    repo = get(record, "repository", {})
    ok = isinstance(repo, dict) and all(exists(repo.get(k)) for k in ["name", "branch", "commit_sha", "timestamp"])
    return ok, {"repository_keys": sorted(repo.keys()) if isinstance(repo, dict) else []}, "Repository, commit, branch, and timestamp context are present."


def build_pipeline_rules() -> list[Rule]:
    t = ToolCode.PIPELINE
    return [
        Rule("PIPE-001", "Pipeline run ID exists", "Pipeline run ID is mandatory.", Severity.CRITICAL, t, field_exists("pipeline_run_id"), "Pipeline run ID is missing.", "PIPELINE_DATA_MISSING"),
        Rule("PIPE-002", "Supported source system", "Pipeline source system must be supported.", Severity.HIGH, t, _supported_source, "Pipeline source system is unsupported.", "PIPELINE_DATA_MISSING"),
        Rule("PIPE-003", "Failure status exists", "A failed status is required.", Severity.CRITICAL, t, field_exists("status"), "Failure status is missing.", "PIPELINE_DATA_MISSING"),
        Rule("PIPE-004", "Failed stage exists", "Failed stage must be identified.", Severity.HIGH, t, field_exists("failed_stage"), "Failed stage is missing.", "PIPELINE_DATA_MISSING"),
        Rule("PIPE-005", "Logs or stack trace exists", "Evidence is required for RCA.", Severity.CRITICAL, t, _logs_or_stack, "Logs and stack trace are missing.", "LOG_EVIDENCE"),
        Rule("PIPE-006", "RCA exists", "Root cause analysis is required.", Severity.HIGH, t, field_exists("rca"), "RCA is missing.", "RCA_QUALITY"),
        Rule("PIPE-007", "RCA references log evidence", "RCA must be traceable to evidence.", Severity.HIGH, t, _rca_references_logs, "RCA does not reference evidence present in logs.", "LOG_EVIDENCE"),
        Rule("PIPE-008", "Remediation exists", "A remediation recommendation is required.", Severity.HIGH, t, field_exists("remediation"), "Recommended remediation is missing.", "REMEDIATION_SAFETY"),
        Rule("PIPE-009", "Proposed change target", "Patch must identify a target when remediation exists.", Severity.MEDIUM, t, _proposed_change_target, "Proposed change does not identify a relevant file or configuration target.", "PR_STRUCTURE"),
        Rule("PIPE-010", "No secret exposure", "Logs and fix details must not expose obvious secrets.", Severity.CRITICAL, t, no_secret_exposure, "Potential secret exposure detected.", "REMEDIATION_SAFETY"),
        Rule("PIPE-011", "No unsafe shell command", "Remediation must not include obviously unsafe commands.", Severity.CRITICAL, t, no_unsafe_shell_command, "Unsafe shell command detected.", "REMEDIATION_SAFETY"),
        Rule("PIPE-012", "Confidence in range", "Agent confidence must be 0 to 1.", Severity.MEDIUM, t, confidence_in_range("confidence"), "Confidence is missing or outside 0 to 1.", "RCA_QUALITY"),
        Rule("PIPE-013", "PR metadata valid", "Optional PR metadata must be valid.", Severity.MEDIUM, t, _pr_valid, "Proposed PR metadata is incomplete.", "PR_STRUCTURE"),
        Rule("PIPE-014", "Post-fix outcome consistent", "Optional post-fix outcome must be valid.", Severity.LOW, t, _rerun_consistent, "Post-fix or rerun outcome is inconsistent.", "POST_FIX_VERIFICATION"),
        Rule("PIPE-015", "Notification output exists", "Teams notification should exist when expected.", Severity.LOW, t, field_exists("notification"), "Notification output is missing.", "NOTIFICATION_QUALITY"),
        Rule("PIPE-016", "Repository context consistent", "Repository, branch, commit, and timestamp must be present.", Severity.MEDIUM, t, _repo_context, "Repository context is incomplete.", "PIPELINE_DATA_MISSING"),
    ]


class PipelineTroubleshootingTool(ToolNode):
    tool_code = ToolCode.PIPELINE
    agent_code = AgentCode.PIPELINE_TROUBLESHOOTING
    summary = "Pipeline failure record and proposed remediation were validated."

    def __init__(self) -> None:
        super().__init__(build_pipeline_rules())
