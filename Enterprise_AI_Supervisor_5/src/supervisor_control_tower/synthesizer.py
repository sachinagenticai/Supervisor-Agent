from __future__ import annotations

from supervisor_control_tower.config import Settings
from supervisor_control_tower.data_science.scorecard import AssuranceScorecard
from supervisor_control_tower.models import (
    AgentDefinition,
    AssuranceBand,
    BusinessDecision,
    FinalSynthesis,
    GovernanceAssessment,
    LlmJudgementResult,
    RuleResultModel,
    Severity,
    ToolResult,
    Verdict,
)
from supervisor_control_tower.remediation import RemediationPlanner


class FinalSynthesizer:
    """Single authoritative, deterministic decision and assurance algorithm."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.high_threshold = settings.high_confidence_threshold
        self.minimum_threshold = settings.minimum_confidence_threshold
        self.scorecard = AssuranceScorecard()
        self.remediation_planner = RemediationPlanner(settings.remediation_proposals_enabled)

    def synthesize(
        self,
        tool_result: ToolResult,
        judgement: LlmJudgementResult,
        *,
        routing_confidence: float = 1.0,
        agent_definition: AgentDefinition | None = None,
        governance: GovernanceAssessment | None = None,
    ) -> FinalSynthesis:
        governance = governance or GovernanceAssessment()
        rules = tool_result.rule_results
        failed = [rule for rule in rules if not rule.passed]
        critical_failed = [rule for rule in failed if rule.severity == Severity.CRITICAL]
        high_medium_failed = [
            rule for rule in failed if rule.severity in {Severity.HIGH, Severity.MEDIUM}
        ]
        data_completeness = self._data_completeness(rules)
        missing_evidence = any(rule.mandatory and not rule.passed for rule in rules)
        disagreement = self._detect_disagreement(rules, judgement)

        thresholds = agent_definition.thresholds if agent_definition else None
        ready_threshold = thresholds.ready_assurance if thresholds else self.high_threshold
        minimum_threshold = thresholds.minimum_assurance if thresholds else self.minimum_threshold
        missing_evidence_cap = thresholds.missing_evidence_cap if thresholds else 0.60

        score = self.scorecard.calculate(
            rules,
            judgement.confidence,
            judgement.quality_dimensions,
            data_completeness,
            routing_confidence,
            degraded_mode=judgement.degraded_mode,
            disagreement_detected=disagreement,
            critical_failure_cap=self.settings.critical_failure_score_cap,
            degraded_mode_cap=self.settings.degraded_mode_score_cap,
            disagreement_penalty=self.settings.disagreement_penalty,
            missing_evidence=missing_evidence,
            missing_evidence_cap=missing_evidence_cap,
        )
        assurance_score = score.final_confidence

        verdict, decision, reason = self._decision(
            tool_result=tool_result,
            judgement=judgement,
            governance=governance,
            critical_failed=critical_failed,
            high_medium_failed=high_medium_failed,
            assurance_score=assurance_score,
            ready_threshold=ready_threshold,
            minimum_threshold=minimum_threshold,
            missing_evidence=missing_evidence,
        )

        remediation = self.remediation_planner.build(tool_result, judgement)
        recommended_action = self._recommended_action(decision, remediation.actions, governance)
        primary_tag = self._primary_tag(
            tool_result,
            judgement,
            critical_failed,
            high_medium_failed,
            failed,
            agent_definition,
        )
        findings_summary = self._findings_summary(failed, judgement)
        assurance_band = self._assurance_band(assurance_score, ready_threshold, minimum_threshold)

        return FinalSynthesis(
            verdict=verdict,
            business_decision=decision,
            assurance_score=assurance_score,
            assurance_band=assurance_band,
            confidence=assurance_score,
            reason=reason,
            primary_tag=primary_tag,
            findings_summary=findings_summary,
            recommended_action=recommended_action,
            data_completeness=data_completeness,
            score_breakdown=score.to_dict(),
            disagreement_detected=disagreement,
            degraded_mode=judgement.degraded_mode,
            governance=governance,
            remediation=remediation,
        )

    @staticmethod
    def _decision(
        *,
        tool_result: ToolResult,
        judgement: LlmJudgementResult,
        governance: GovernanceAssessment,
        critical_failed: list[RuleResultModel],
        high_medium_failed: list[RuleResultModel],
        assurance_score: float,
        ready_threshold: float,
        minimum_threshold: float,
        missing_evidence: bool,
    ) -> tuple[Verdict, BusinessDecision, str]:
        if not tool_result.execution_success:
            return Verdict.FAIL, BusinessDecision.BLOCKED, "The selected validation tool did not complete successfully."
        if governance.status == BusinessDecision.BLOCKED:
            return Verdict.FAIL, BusinessDecision.BLOCKED, governance.reasons[0]
        if critical_failed:
            return (
                Verdict.FAIL,
                BusinessDecision.BLOCKED,
                f"Critical control failure: {critical_failed[0].message}",
            )
        if judgement.verdict == Verdict.FAIL:
            return Verdict.FAIL, BusinessDecision.BLOCKED, f"LLM Judge blocked the output: {judgement.reason}"
        if assurance_score < minimum_threshold:
            return (
                Verdict.FAIL,
                BusinessDecision.BLOCKED,
                f"AI Assurance Score {assurance_score:.0%} is below the minimum threshold {minimum_threshold:.0%}.",
            )
        if missing_evidence:
            return (
                Verdict.WARNING,
                BusinessDecision.NEEDS_REVIEW,
                "Mandatory evidence is incomplete; human review is required before promotion.",
            )
        if governance.status == BusinessDecision.NEEDS_REVIEW:
            return Verdict.WARNING, BusinessDecision.NEEDS_REVIEW, governance.reasons[0]
        if high_medium_failed:
            return (
                Verdict.WARNING,
                BusinessDecision.NEEDS_REVIEW,
                f"Material control gap requires review: {high_medium_failed[0].message}",
            )
        if judgement.verdict == Verdict.WARNING:
            return Verdict.WARNING, BusinessDecision.NEEDS_REVIEW, judgement.reason
        if assurance_score < ready_threshold:
            return (
                Verdict.WARNING,
                BusinessDecision.NEEDS_REVIEW,
                f"AI Assurance Score {assurance_score:.0%} is below the ready threshold {ready_threshold:.0%}.",
            )
        return (
            Verdict.PASS,
            BusinessDecision.READY,
            "The output is evidence-supported, mandatory controls passed and no critical risk was identified.",
        )

    @staticmethod
    def _data_completeness(rules: list[RuleResultModel]) -> float:
        evidence_rules = [
            rule
            for rule in rules
            if rule.mandatory
            or any(
                token in rule.tag.upper()
                for token in ("MISSING", "COMPLETENESS", "EVIDENCE", "DATA", "IDENTITY")
            )
        ]
        if not evidence_rules:
            return 1.0
        return round(
            len([rule for rule in evidence_rules if rule.passed]) / len(evidence_rules),
            3,
        )

    @staticmethod
    def _detect_disagreement(
        rules: list[RuleResultModel], judgement: LlmJudgementResult
    ) -> bool:
        has_material_failure = any(
            (not rule.passed) and rule.severity in {Severity.CRITICAL, Severity.HIGH}
            for rule in rules
        )
        all_material_pass = not has_material_failure
        return (has_material_failure and judgement.verdict == Verdict.PASS) or (
            all_material_pass and judgement.verdict == Verdict.FAIL
        )

    @staticmethod
    def _assurance_band(score: float, high: float, minimum: float) -> AssuranceBand:
        if score >= high:
            return AssuranceBand.HIGH
        if score >= minimum:
            return AssuranceBand.MEDIUM
        return AssuranceBand.LOW

    @staticmethod
    def _findings_summary(
        failed: list[RuleResultModel], judgement: LlmJudgementResult
    ) -> list[str]:
        ordered_rules = sorted(
            failed,
            key=lambda rule: {
                Severity.CRITICAL: 0,
                Severity.HIGH: 1,
                Severity.MEDIUM: 2,
                Severity.LOW: 3,
                Severity.INFO: 4,
            }[rule.severity],
        )
        messages = [rule.message for rule in ordered_rules]
        messages.extend(finding.message for finding in judgement.findings)
        unique: list[str] = []
        for message in messages:
            if message and message not in unique:
                unique.append(message)
            if len(unique) >= 5:
                break
        return unique

    @staticmethod
    def _recommended_action(
        decision: BusinessDecision,
        actions: list,
        governance: GovernanceAssessment,
    ) -> str:
        if governance.required_approvals:
            return f"Obtain pending approval from {', '.join(governance.required_approvals)} and rerun the evaluation."
        if decision == BusinessDecision.READY:
            return "Proceed to the next controlled approval or release stage and retain this evidence for audit."
        if actions:
            return actions[0].action
        if decision == BusinessDecision.NEEDS_REVIEW:
            return "Assign the result to the responsible reviewer, resolve the material gaps and rerun the evaluation."
        return "Block promotion, resolve the critical issue and rerun the evaluation before any downstream action."

    @staticmethod
    def _primary_tag(
        tool_result: ToolResult,
        judgement: LlmJudgementResult,
        critical_failed: list[RuleResultModel],
        high_medium_failed: list[RuleResultModel],
        failed: list[RuleResultModel],
        agent_definition: AgentDefinition | None,
    ) -> str:
        if critical_failed:
            return critical_failed[0].tag
        if high_medium_failed:
            return sorted(
                high_medium_failed,
                key=lambda rule: 0 if rule.severity == Severity.HIGH else 1,
            )[0].tag
        if judgement.findings:
            return judgement.findings[0].tag
        if failed:
            return failed[0].tag
        if agent_definition:
            return agent_definition.success_tag
        return f"{tool_result.agent_code}_VALIDATED"
