from __future__ import annotations

from supervisor_control_tower.judge import LlmJudge
from supervisor_control_tower.models import LlmJudgementResult, RuleResultModel, Severity, ToolResult, Verdict, ToolCode, AgentCode
from supervisor_control_tower.synthesizer import FinalSynthesizer
from supervisor_control_tower.data_science.scorecard import ConfidenceScorecard


def rr(code: str, severity: Severity, passed: bool, tag: str = "TAG") -> RuleResultModel:
    return RuleResultModel(rule_code=code, rule_name=code, severity=severity, passed=passed, evidence={}, message=f"{code} message", tag=tag)


def tool_result(rules):
    return ToolResult(tool_code=ToolCode.PIPELINE, agent_code=AgentCode.PIPELINE_TROUBLESHOOTING, summary="s", rule_results=rules)


def judgement(verdict=Verdict.PASS, confidence=0.9):
    return LlmJudgementResult(verdict=verdict, confidence=confidence, reason="ok", findings=[])


def test_pass_synthesis(settings):
    final = FinalSynthesizer(settings).synthesize(tool_result([rr("a", Severity.HIGH, True), rr("b", Severity.CRITICAL, True)]), judgement())
    assert final.verdict == Verdict.PASS
    assert final.confidence >= 0.8


def test_warning_synthesis_for_medium_failure(settings):
    final = FinalSynthesizer(settings).synthesize(tool_result([rr("a", Severity.MEDIUM, False)]), judgement(Verb=Verdict.PASS) if False else judgement())
    assert final.verdict == Verdict.WARNING


def test_fail_synthesis_for_critical_failure(settings):
    final = FinalSynthesizer(settings).synthesize(tool_result([rr("a", Severity.CRITICAL, False, "CRIT")]), judgement())
    assert final.verdict == Verdict.FAIL
    assert final.primary_tag == "CRIT"


def test_confidence_formula_penalizes_failures(settings):
    scorecard = ConfidenceScorecard()
    high = scorecard.calculate([rr("a", Severity.CRITICAL, True), rr("b", Severity.HIGH, True)], 0.9, 1.0)
    low = scorecard.calculate([rr("a", Severity.CRITICAL, False), rr("b", Severity.HIGH, True)], 0.9, 0.5)
    assert high.final_confidence > low.final_confidence
    assert high.severity_weighted_rule_score > low.severity_weighted_rule_score


def test_mock_llm_output_validation(llm, pipeline_record):
    tool = tool_result([rr("a", Severity.HIGH, True)])
    result = LlmJudge(llm).evaluate(pipeline_record, tool)
    assert result.verdict in {Verdict.PASS, Verdict.WARNING, Verdict.FAIL}
    assert 0 <= result.confidence <= 1
