from __future__ import annotations

import re
from datetime import datetime

from supervisor_control_tower.models import AgentCode, NormalizedRecord, Severity, ToolCode
from supervisor_control_tower.rules.engine import Rule, exists, field_exists, get
from supervisor_control_tower.tools.base import ToolNode


def _sprint_goal(record: NormalizedRecord):
    required = bool(get(record, "sprint_required", True))
    ok = True if not required else exists(get(record, "sprint_id")) and exists(get(record, "sprint_goal"))
    return ok, {"sprint_required": required, "sprint_id": get(record, "sprint_id")}, "Sprint ID and goal exist when needed."


def _acceptance_testable(record: NormalizedRecord):
    criteria = get(record, "acceptance_criteria", [])
    verbs = ("given", "when", "then", "verify", "should", "must")
    ok = isinstance(criteria, list) and len(criteria) > 0 and all(any(v in str(c).lower() for v in verbs) for c in criteria)
    return ok, {"criteria_count": len(criteria) if isinstance(criteria, list) else 0}, "Acceptance criteria exist and are testable."


def _status_aligns(record: NormalizedRecord):
    issues = get(record, "issues", [])
    summary = str(get(record, "sprint_status", "")).lower()
    done = [i for i in issues if isinstance(i, dict) and str(i.get("status", "")).lower() in {"done", "closed", "completed"}]
    open_items = [i for i in issues if isinstance(i, dict) and str(i.get("status", "")).lower() not in {"done", "closed", "completed"}]
    ok = bool(summary) and ((open_items and "open" in summary or "risk" in summary or "in progress" in summary) or (not open_items and ("complete" in summary or "done" in summary)))
    return ok, {"done_count": len(done), "open_count": len(open_items)}, "Status summary aligns with issue statuses."


def _repo_deployment_represented(record: NormalizedRecord):
    pr_status = str(get(record, "pr_status", "")).lower()
    deployment_status = str(get(record, "deployment_status", "")).lower()
    summary = str(get(record, "sprint_status", "")).lower()
    ok = exists(pr_status) and exists(deployment_status) and pr_status in summary and deployment_status in summary
    return ok, {"pr_status": pr_status, "deployment_status": deployment_status}, "Merged PR and deployment states are represented correctly."


def _blocker_evidence(record: NormalizedRecord):
    blockers = get(record, "blockers", [])
    if not blockers:
        return True, {"blocker_count": 0}, "No blockers are claimed."
    ok = all(exists(b.get("source")) and exists(b.get("message")) for b in blockers if isinstance(b, dict))
    return ok, {"blocker_count": len(blockers)}, "Blockers have source evidence."


def _velocity_valid(record: NormalizedRecord):
    velocity = get(record, "velocity")
    ok = isinstance(velocity, (int, float)) and velocity >= 0
    return ok, {"velocity": velocity}, "Velocity is valid and non-negative."


def _consistent_time_window(record: NormalizedRecord):
    window = get(record, "analysis_window", {})
    try:
        start = datetime.fromisoformat(str(window.get("start")))
        end = datetime.fromisoformat(str(window.get("end")))
        ok = start < end
    except Exception:
        ok = False
    return ok, {"analysis_window": window}, "Calculations use a consistent time window."


def _recommendation_capacity(record: NormalizedRecord):
    capacity = get(record, "capacity", {})
    rec = str(get(record, "planning_recommendation", "")).lower()
    available = capacity.get("available_points") if isinstance(capacity, dict) else None
    requested = capacity.get("recommended_points") if isinstance(capacity, dict) else None
    ok = not isinstance(available, (int, float)) or not isinstance(requested, (int, float)) or requested <= available
    return ok and exists(rec), {"available_points": available, "recommended_points": requested}, "Recommendations do not contradict capacity."


def _duplicate_stories(record: NormalizedRecord):
    new_title = str(get(record, "generated_story.title", "")).lower()
    backlog = get(record, "backlog", [])
    normalized = lambda s: re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()
    duplicates = [b.get("title") for b in backlog if isinstance(b, dict) and normalized(b.get("title")) == normalized(new_title)]
    return not duplicates, {"duplicates": duplicates}, "No duplicate story found by normalized matching."


def _ownership_consistent(record: NormalizedRecord):
    assignee = get(record, "generated_story.assignee")
    team = get(record, "assignees", [])
    ok = not exists(assignee) or assignee in team
    return ok, {"assignee": assignee, "known_assignees": team}, "Ownership is consistent."


def _risk_claim_dates(record: NormalizedRecord):
    risks = get(record, "risks", [])
    bad = [r for r in risks if isinstance(r, dict) and ("overdue" in str(r.get("message", "")).lower() or "at risk" in str(r.get("message", "")).lower()) and not exists(r.get("date_evidence"))]
    return not bad, {"unsupported_claims": len(bad)}, "Overdue or at-risk claims are supported by dates."


def _completed_work_not_invented(record: NormalizedRecord):
    completed = get(record, "completed_work", [])
    repo = set(get(record, "repo_activity.completed_items", []) or [])
    missing = [c for c in completed if c not in repo]
    return not missing, {"unsupported_completed_work": missing}, "Completed work is backed by repository or deployment data."


def build_project_rules() -> list[Rule]:
    t = ToolCode.PROJECT
    return [
        Rule("PM-001", "Project or board exists", "Project or board ID is mandatory.", Severity.CRITICAL, t, field_exists("board_id"), "Project or board ID is missing.", "SPRINT_STATUS"),
        Rule("PM-002", "Sprint ID and goal", "Sprint info is required when needed.", Severity.HIGH, t, _sprint_goal, "Sprint ID or goal is missing.", "SPRINT_STATUS"),
        Rule("PM-003", "Story title", "Generated story must have a title.", Severity.HIGH, t, field_exists("generated_story.title"), "Generated story title is missing.", "STORY_QUALITY"),
        Rule("PM-004", "Story description", "Generated story must have a description.", Severity.HIGH, t, field_exists("generated_story.description"), "Generated story description is missing.", "STORY_QUALITY"),
        Rule("PM-005", "Acceptance criteria", "Acceptance criteria must be testable.", Severity.HIGH, t, _acceptance_testable, "Acceptance criteria are missing or not testable.", "ACCEPTANCE_CRITERIA"),
        Rule("PM-006", "Status aligns", "Status summary must align with issue statuses.", Severity.HIGH, t, _status_aligns, "Status summary does not align with issue statuses.", "SPRINT_STATUS"),
        Rule("PM-007", "Repo deployment represented", "PR and deployment states must be reflected.", Severity.HIGH, t, _repo_deployment_represented, "PR or deployment state is not represented correctly.", "REPOSITORY_ALIGNMENT"),
        Rule("PM-008", "Blocker evidence", "Blockers must cite evidence.", Severity.MEDIUM, t, _blocker_evidence, "Blockers do not have source evidence.", "BLOCKER_EVIDENCE"),
        Rule("PM-009", "Velocity valid", "Velocity must be non-negative.", Severity.MEDIUM, t, _velocity_valid, "Velocity is missing or negative.", "VELOCITY_ANALYSIS"),
        Rule("PM-010", "Time window consistent", "Analysis window must be valid.", Severity.MEDIUM, t, _consistent_time_window, "Calculations use an inconsistent time window.", "VELOCITY_ANALYSIS"),
        Rule("PM-011", "Recommendation capacity", "Recommendation must not exceed capacity.", Severity.MEDIUM, t, _recommendation_capacity, "Recommendation contradicts available capacity.", "CAPACITY_INSIGHT"),
        Rule("PM-012", "Duplicate story detection", "Generated story should not duplicate backlog.", Severity.MEDIUM, t, _duplicate_stories, "A duplicate story was detected.", "STORY_QUALITY"),
        Rule("PM-013", "Ownership consistent", "Assignee should exist in team assignees.", Severity.LOW, t, _ownership_consistent, "Ownership is inconsistent.", "CAPACITY_INSIGHT"),
        Rule("PM-014", "Risk dates supported", "Risk claims must include date evidence.", Severity.MEDIUM, t, _risk_claim_dates, "Overdue or at-risk claims lack date evidence.", "SCHEDULE_RISK"),
        Rule("PM-015", "Completed work backed", "Completed work must be backed by repo/deployment data.", Severity.CRITICAL, t, _completed_work_not_invented, "Completed work is invented or unsupported.", "REPOSITORY_ALIGNMENT"),
    ]


class ProjectManagementTool(ToolNode):
    tool_code = ToolCode.PROJECT
    agent_code = AgentCode.PROJECT_MANAGEMENT
    summary = "Project management story, sprint status, blockers, and planning insights were validated."

    def __init__(self) -> None:
        super().__init__(build_project_rules())
