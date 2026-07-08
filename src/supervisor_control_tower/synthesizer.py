from __future__ import annotations

from supervisor_control_tower.config import Settings
from supervisor_control_tower.data_science.scorecard import ConfidenceScorecard
from supervisor_control_tower.models import FinalSynthesis, LlmJudgementResult, RuleResultModel, Severity, ToolResult, Verdict

SUCCESS_TAG = {
    "pipeline_troubleshooting_tool": "PIPELINE_VALIDATED",
    "infrastructure_provisioning_tool": "INFRA_VALIDATED",
    "finops_optimization_tool": "FINOPS_VALIDATED",
    "project_management_tool": "PROJECT_VALIDATED",
}


class FinalSynthesizer:
    """LLM-first final verdict logic.

    The LLM Judge is the primary signal. The deterministic rule engine acts as a
    safety net — it can force a FAIL for CRITICAL violations but cannot override
    a PASS verdict up to WARNING without LLM agreement.
    """

    def __init__(self, settings: Settings):
        self.high_threshold = settings.high_confidence_threshold
        self.minimum_threshold = settings.minimum_confidence_threshold
        self.scorecard = ConfidenceScorecard()

    def synthesize(self, tool_result: ToolResult, judgement: LlmJudgementResult) -> FinalSynthesis:
        rules = tool_result.rule_results
        failed = [r for r in rules if not r.passed]
        critical_failed = [r for r in failed if r.severity == Severity.CRITICAL]
        data_completeness = self._data_completeness(rules)

        # ── LLM quality dimensions (if available) ────────────────────────
        qd = judgement.quality_dimensions or {}
        safety_score = qd.get("safety", 1.0)

        # ── Confidence: LLM is primary, scorecard as secondary blend ─────
        # If LLM returned quality dimensions, blend into confidence
        if qd:
            dim_avg = sum(qd.values()) / len(qd)
            confidence = round(0.70 * judgement.confidence + 0.30 * dim_avg, 3)
        else:
            confidence = judgement.confidence

        final_tag = self._primary_tag(tool_result, judgement, critical_failed, failed)

        # ── Verdict: LLM is primary, hard safety overrides only ──────────
        # Only two hard overrides from deterministic rules:
        # 1. CRITICAL rule failure → always FAIL (safety contract)
        # 2. Tool execution failure → always FAIL
        if not tool_result.execution_success:
            verdict = Verdict.FAIL
            reason = "Selected tool could not complete validation."
        elif safety_score == 0.0 or any("CREDENTIAL" in r.tag or "SAFETY" in r.tag for r in critical_failed):
            # Hard safety block — dangerous output regardless of LLM opinion
            verdict = Verdict.FAIL
            reason = (
                f"Safety violation detected: {critical_failed[0].message}"
                if critical_failed
                else "LLM safety score is zero — unsafe output detected."
            )
        elif critical_failed and judgement.verdict != Verdict.FAIL:
            # CRITICAL rule fail but LLM said PASS/WARNING — trust both, take stricter
            verdict = Verdict.FAIL
            reason = f"Critical rule violation overrides LLM verdict: {critical_failed[0].message}"
        else:
            # ── Pure LLM-driven verdict ───────────────────────────────────
            verdict = judgement.verdict
            reason = judgement.reason

        return FinalSynthesis(
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            primary_tag=final_tag,
            findings_summary=[f.message for f in judgement.findings[:5]] + [r.message for r in critical_failed[:2]],
            data_completeness=data_completeness,
            score_breakdown=self._build_score_breakdown(judgement, confidence, data_completeness),
        )

    def _build_score_breakdown(
        self, judgement: LlmJudgementResult, final_confidence: float, data_completeness: float
    ) -> dict[str, float]:
        bd: dict[str, float] = {"llm_confidence": judgement.confidence, "data_completeness": data_completeness}
        qd = judgement.quality_dimensions or {}
        bd.update({k: round(v, 3) for k, v in qd.items()})
        bd["final_confidence"] = final_confidence
        return bd

    def _data_completeness(self, rules: list[RuleResultModel]) -> float:
        data_rules = [r for r in rules if "MISSING" in r.tag or "COMPLETENESS" in r.tag or "DATA" in r.tag]
        if not data_rules:
            return 1.0
        return round(len([r for r in data_rules if r.passed]) / len(data_rules), 2)

    def _primary_tag(
        self,
        tool_result: ToolResult,
        judgement: LlmJudgementResult,
        critical_failed: list[RuleResultModel],
        failed: list[RuleResultModel],
    ) -> str:
        if critical_failed:
            return critical_failed[0].tag
        if judgement.findings:
            sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
            top = sorted(judgement.findings, key=lambda f: sev_order.get(f.severity.value if hasattr(f.severity, "value") else str(f.severity), 5))
            return top[0].tag if top else judgement.findings[0].tag
        if failed:
            return failed[0].tag
        return SUCCESS_TAG.get(tool_result.tool_code.value, "VALIDATED")
    """Deterministic final verdict logic.

    The final verdict is not an LLM decision. It is an explainable scorecard over
    rule results, LLM judge confidence, and data-completeness signals.
    """

    def __init__(self, settings: Settings):
        self.high_threshold = settings.high_confidence_threshold
        self.minimum_threshold = settings.minimum_confidence_threshold
        self.scorecard = ConfidenceScorecard()

    def synthesize(self, tool_result: ToolResult, judgement: LlmJudgementResult) -> FinalSynthesis:
        rules = tool_result.rule_results
        failed = [r for r in rules if not r.passed]
        critical_failed = [r for r in failed if r.severity == Severity.CRITICAL]
        high_medium_failed = [r for r in failed if r.severity in {Severity.HIGH, Severity.MEDIUM}]
        data_completeness = self._data_completeness(rules)
        score = self.scorecard.calculate(rules, judgement.confidence, data_completeness)
        confidence = score.final_confidence
        final_tag = self._primary_tag(tool_result, judgement, critical_failed, high_medium_failed, failed)

        if critical_failed:
            verdict = Verdict.FAIL
            reason = f"Critical validation failure: {critical_failed[0].message}"
        elif not tool_result.execution_success:
            verdict = Verdict.FAIL
            reason = "Selected tool could not complete validation."
        elif judgement.verdict == Verdict.FAIL:
            verdict = Verdict.FAIL
            reason = f"LLM Judge failed the record: {judgement.reason}"
        elif confidence < self.minimum_threshold:
            verdict = Verdict.FAIL
            reason = f"Final confidence {confidence:.2f} is below minimum threshold {self.minimum_threshold:.2f}."
        elif high_medium_failed:
            verdict = Verdict.WARNING
            reason = f"Human review recommended: {high_medium_failed[0].message}"
        elif judgement.verdict == Verdict.WARNING:
            verdict = Verdict.WARNING
            reason = f"LLM Judge issued warning: {judgement.reason}"
        elif confidence < self.high_threshold:
            verdict = Verdict.WARNING
            reason = f"Final confidence {confidence:.2f} is below high-confidence threshold {self.high_threshold:.2f}."
        else:
            verdict = Verdict.PASS
            reason = "All mandatory checks passed and the LLM Judge found the output supported by the evidence."

        return FinalSynthesis(
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            primary_tag=final_tag,
            findings_summary=[r.message for r in failed[:5]] + [f.message for f in judgement.findings[:3]],
            data_completeness=data_completeness,
            score_breakdown=score.to_dict(),
        )

    def _data_completeness(self, rules: list[RuleResultModel]) -> float:
        data_rules = [r for r in rules if "MISSING" in r.tag or "COMPLETENESS" in r.tag or "DATA" in r.tag]
        if not data_rules:
            return 1.0
        return round(len([r for r in data_rules if r.passed]) / len(data_rules), 2)

    def _primary_tag(
        self,
        tool_result: ToolResult,
        judgement: LlmJudgementResult,
        critical_failed: list[RuleResultModel],
        high_medium_failed: list[RuleResultModel],
        failed: list[RuleResultModel],
    ) -> str:
        if critical_failed:
            return critical_failed[0].tag
        if high_medium_failed:
            order = {Severity.HIGH: 0, Severity.MEDIUM: 1}
            return sorted(high_medium_failed, key=lambda r: order[r.severity])[0].tag
        if judgement.findings:
            return judgement.findings[0].tag
        if failed:
            return failed[0].tag
        return SUCCESS_TAG.get(tool_result.tool_code.value, "VALIDATED")
