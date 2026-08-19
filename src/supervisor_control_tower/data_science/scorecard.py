from __future__ import annotations

from dataclasses import asdict, dataclass

from supervisor_control_tower.models import RuleResultModel, Severity


SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 8.0,
    Severity.HIGH: 5.0,
    Severity.MEDIUM: 3.0,
    Severity.LOW: 1.5,
    Severity.INFO: 0.5,
}


@dataclass(frozen=True)
class ScorecardBreakdown:
    passed_rule_ratio: float
    severity_weighted_rule_score: float
    llm_confidence: float
    quality_dimension_score: float
    data_completeness: float
    routing_confidence: float
    base_assurance_score: float
    disagreement_penalty: float
    final_confidence: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


class AssuranceScorecard:
    """Explainable governance score; not a calibrated probability."""

    def calculate(
        self,
        rules: list[RuleResultModel],
        llm_confidence: float,
        quality_dimensions: dict[str, float] | float | None = None,
        data_completeness: float = 1.0,
        routing_confidence: float = 1.0,
        *,
        degraded_mode: bool = False,
        disagreement_detected: bool = False,
        critical_failure_cap: float = 0.40,
        degraded_mode_cap: float = 0.70,
        disagreement_penalty: float = 0.15,
        missing_evidence: bool = False,
        missing_evidence_cap: float = 0.60,
    ) -> ScorecardBreakdown:
        # Compatibility: the previous scorecard accepted the third positional
        # argument as data completeness. Numeric input is interpreted that way.
        if isinstance(quality_dimensions, (int, float)):
            data_completeness = float(quality_dimensions)
            quality_dimensions = {}
        quality_dimensions = quality_dimensions or {}

        passed_rule_ratio = (
            len([rule for rule in rules if rule.passed]) / len(rules) if rules else 0.0
        )
        total_weight = sum(SEVERITY_WEIGHT[rule.severity] for rule in rules)
        passed_weight = sum(SEVERITY_WEIGHT[rule.severity] for rule in rules if rule.passed)
        severity_score = passed_weight / total_weight if total_weight else passed_rule_ratio

        quality_score = (
            sum(float(value) for value in quality_dimensions.values()) / len(quality_dimensions)
            if quality_dimensions
            else float(llm_confidence)
        )

        base_score = (
            0.30 * severity_score
            + 0.25 * float(llm_confidence)
            + 0.20 * quality_score
            + 0.15 * float(data_completeness)
            + 0.10 * float(routing_confidence)
        )
        applied_penalty = disagreement_penalty if disagreement_detected else 0.0
        final_score = base_score - applied_penalty

        if any((not rule.passed) and rule.severity == Severity.CRITICAL for rule in rules):
            final_score = min(final_score, critical_failure_cap)
        if degraded_mode:
            final_score = min(final_score, degraded_mode_cap)
        if missing_evidence:
            final_score = min(final_score, missing_evidence_cap)

        clamp = lambda value: round(max(0.0, min(1.0, float(value))), 3)
        return ScorecardBreakdown(
            passed_rule_ratio=clamp(passed_rule_ratio),
            severity_weighted_rule_score=clamp(severity_score),
            llm_confidence=clamp(llm_confidence),
            quality_dimension_score=clamp(quality_score),
            data_completeness=clamp(data_completeness),
            routing_confidence=clamp(routing_confidence),
            base_assurance_score=clamp(base_score),
            disagreement_penalty=clamp(applied_penalty),
            final_confidence=clamp(final_score),
        )


# Backwards-compatible name used by previous tests and notebooks.
ConfidenceScorecard = AssuranceScorecard
