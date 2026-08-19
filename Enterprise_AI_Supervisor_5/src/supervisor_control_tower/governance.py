from __future__ import annotations

from typing import Any

from supervisor_control_tower.models import BusinessDecision, GovernanceAssessment, NormalizedRecord


class GovernanceEngine:
    """Lightweight cross-agent dependency and approval governance."""

    def assess(self, record: NormalizedRecord, repository: object) -> GovernanceAssessment:
        reasons: list[str] = []
        dependency_results: list[dict[str, Any]] = []
        required_approvals = [str(item) for item in record.metadata.get("required_approvals", [])]
        approvals = record.metadata.get("approvals", {})
        missing_approvals = [
            approval
            for approval in required_approvals
            if str((approvals or {}).get(approval, "")).lower() not in {"approved", "accepted"}
        ]

        status = BusinessDecision.READY
        dependencies = record.metadata.get("dependencies", [])
        for dependency in dependencies if isinstance(dependencies, list) else []:
            if isinstance(dependency, str):
                external_reference = dependency
                mandatory = True
            elif isinstance(dependency, dict):
                external_reference = str(dependency.get("external_reference") or "")
                mandatory = bool(dependency.get("mandatory", True))
            else:
                continue
            if not external_reference:
                continue
            latest = (
                repository.latest_decision_for_external_reference(external_reference)
                if hasattr(repository, "latest_decision_for_external_reference")
                else None
            )
            decision = str((latest or {}).get("business_decision") or "NOT_EVALUATED")
            dependency_results.append(
                {
                    "external_reference": external_reference,
                    "mandatory": mandatory,
                    "decision": decision,
                    "run_id": (latest or {}).get("run_id"),
                }
            )
            if mandatory and decision != BusinessDecision.READY.value:
                status = BusinessDecision.BLOCKED
                reasons.append(
                    f"Mandatory upstream dependency {external_reference} is {decision.replace('_', ' ').title()}."
                )
            elif not mandatory and decision != BusinessDecision.READY.value and status != BusinessDecision.BLOCKED:
                status = BusinessDecision.NEEDS_REVIEW
                reasons.append(f"Optional upstream dependency {external_reference} is not ready.")

        if missing_approvals and status != BusinessDecision.BLOCKED:
            status = BusinessDecision.NEEDS_REVIEW
            reasons.append(f"Pending approvals: {', '.join(missing_approvals)}.")

        if not reasons:
            reasons.append("No unresolved cross-agent dependency or approval issue was found.")
        return GovernanceAssessment(
            status=status,
            reasons=reasons,
            dependency_results=dependency_results,
            required_approvals=missing_approvals,
        )
