from __future__ import annotations

from dataclasses import asdict, dataclass

from supervisor_control_tower.models import RuleResultModel, Severity


SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 5.0,
    Severity.HIGH: 3.0,
    Severity.MEDIUM: 2.0,
    Severity.LOW: 1.0,
    Severity.INFO: 0.25,
}


@dataclass(frozen=True)
class ScorecardBreakdown:
    """Transparent components used for final confidence.

    This is deliberately a simple scorecard rather than a trained model. It gives
    demo stakeholders a readable data-science layer while remaining deterministic,
    explainable, and unit-testable.
    """

    passed_rule_ratio: float
    severity_weighted_rule_score: float
    llm_confidence: float
    data_completeness: float
    final_confidence: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


class ConfidenceScorecard:
    def calculate(self, rules: list[RuleResultModel], llm_confidence: float, data_completeness: float) -> ScorecardBreakdown:
        if not rules:
            confidence = min(float(llm_confidence), float(data_completeness))
            return ScorecardBreakdown(
                passed_rule_ratio=0.0,
                severity_weighted_rule_score=0.0,
                llm_confidence=round(float(llm_confidence), 2),
                data_completeness=round(float(data_completeness), 2),
                final_confidence=round(max(0.0, min(1.0, confidence)), 2),
            )

        passed_rule_ratio = len([r for r in rules if r.passed]) / len(rules)
        total_weight = sum(SEVERITY_WEIGHT[r.severity] for r in rules)
        passed_weight = sum(SEVERITY_WEIGHT[r.severity] for r in rules if r.passed)
        severity_weighted_rule_score = passed_weight / total_weight if total_weight else passed_rule_ratio

        confidence = (
            0.30 * passed_rule_ratio
            + 0.35 * severity_weighted_rule_score
            + 0.25 * float(llm_confidence)
            + 0.10 * float(data_completeness)
        )

        has_critical_failure = any((not r.passed) and r.severity == Severity.CRITICAL for r in rules)
        if not has_critical_failure and llm_confidence >= 0.80 and data_completeness >= 0.80:
            confidence = max(confidence, 0.62)

        return ScorecardBreakdown(
            passed_rule_ratio=round(max(0.0, min(1.0, passed_rule_ratio)), 2),
            severity_weighted_rule_score=round(max(0.0, min(1.0, severity_weighted_rule_score)), 2),
            llm_confidence=round(max(0.0, min(1.0, float(llm_confidence))), 2),
            data_completeness=round(max(0.0, min(1.0, float(data_completeness))), 2),
            final_confidence=round(max(0.0, min(1.0, confidence)), 2),
        )
