from __future__ import annotations

from supervisor_control_tower.models import (
    LlmJudgementResult,
    RemediationAction,
    RemediationPlan,
    Severity,
    ToolResult,
)


class RemediationPlanner:
    """Creates human-reviewable actions; it never performs external write-back."""

    def __init__(self, proposals_enabled: bool = True):
        self.proposals_enabled = proposals_enabled

    def build(self, tool_result: ToolResult, judgement: LlmJudgementResult) -> RemediationPlan:
        actions: list[RemediationAction] = []
        if not self.proposals_enabled:
            return RemediationPlan(
                status="DISABLED",
                execution_enabled=False,
                actions=[],
                safety_note="Remediation proposals are disabled by configuration.",
            )
        for result in [item for item in tool_result.rule_results if not item.passed][:4]:
            actions.append(
                RemediationAction(
                    priority=result.severity,
                    action=f"Resolve {result.rule_name.lower()}: {result.message}",
                    source=f"rule:{result.rule_code}",
                )
            )
        for recommendation in judgement.recommendations:
            if len(actions) >= 6:
                break
            if any(recommendation.action.lower() == action.action.lower() for action in actions):
                continue
            actions.append(
                RemediationAction(
                    priority=recommendation.priority,
                    action=recommendation.action,
                    source="llm_judge",
                )
            )
        if not actions:
            actions.append(
                RemediationAction(
                    priority=Severity.INFO,
                    action="No remediation is required. Retain the evaluation evidence for audit.",
                    source="supervisor",
                )
            )
        return RemediationPlan(
            status="APPROVAL_REQUIRED" if actions else "NOT_REQUIRED",
            execution_enabled=False,
            actions=actions,
        )
