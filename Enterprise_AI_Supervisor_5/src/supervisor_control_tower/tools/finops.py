from __future__ import annotations

from datetime import datetime

from supervisor_control_tower.models import AgentCode, NormalizedRecord, Severity, ToolCode
from supervisor_control_tower.rules.engine import Rule, exists, field_exists, get
from supervisor_control_tower.tools.base import ToolNode


def _resource_id_type(record: NormalizedRecord):
    resources = get(record, "resources", [])
    ok = isinstance(resources, list) and len(resources) > 0 and all(exists(r.get("resource_id")) and exists(r.get("resource_type")) for r in resources if isinstance(r, dict))
    return ok, {"resource_count": len(resources) if isinstance(resources, list) else 0}, "Resource ID and type exist."


def _telemetry_period(record: NormalizedRecord):
    period = get(record, "telemetry_period", {})
    ok = isinstance(period, dict) and exists(period.get("start")) and exists(period.get("end"))
    return ok, {"period": period}, "Telemetry period exists."


def _utilization_data(record: NormalizedRecord):
    resources = get(record, "resources", [])
    ok = isinstance(resources, list) and all(isinstance(r.get("utilization"), dict) and len(r.get("utilization", {})) > 0 for r in resources if isinstance(r, dict))
    return ok and bool(resources), {"resource_count": len(resources) if isinstance(resources, list) else 0}, "Relevant utilization data exists."


def _cost_data_when_savings(record: NormalizedRecord):
    savings = float(get(record, "estimated_monthly_savings", 0) or 0)
    cost = get(record, "current_monthly_cost")
    ok = savings <= 0 or (isinstance(cost, (int, float)) and cost >= 0)
    return ok, {"savings": savings, "current_monthly_cost": cost}, "Cost data exists when savings are claimed."


def _classification_evidence(record: NormalizedRecord):
    recs = get(record, "recommendations", [])
    ok = isinstance(recs, list) and len(recs) > 0 and all(exists(r.get("classification")) and exists(r.get("evidence")) for r in recs if isinstance(r, dict))
    return ok, {"recommendation_count": len(recs) if isinstance(recs, list) else 0}, "Idle or oversized classification has evidence."


def _recommendation_matches_utilization(record: NormalizedRecord):
    recs = get(record, "recommendations", [])
    ok = True
    mismatches = []
    for rec in recs if isinstance(recs, list) else []:
        classification = str(rec.get("classification", "")).lower()
        action = str(rec.get("action", "")).lower()
        if "idle" in classification and not any(word in action for word in ["stop", "deallocate", "delete", "review"]):
            ok = False
            mismatches.append(rec.get("resource_id"))
        if "oversized" in classification and not any(word in action for word in ["rightsize", "resize", "downsize", "review"]):
            ok = False
            mismatches.append(rec.get("resource_id"))
    return ok, {"mismatches": mismatches}, "Recommendation matches utilization pattern."


def _savings_non_negative(record: NormalizedRecord):
    value = get(record, "estimated_monthly_savings")
    ok = isinstance(value, (int, float)) and value >= 0
    return ok, {"estimated_monthly_savings": value}, "Estimated savings is non-negative."


def _savings_not_exceed_cost(record: NormalizedRecord):
    savings = get(record, "estimated_monthly_savings")
    cost = get(record, "current_monthly_cost")
    # Missing cost is handled by FIN-005 as a data-completeness warning.
    # This critical check only fires when both numbers exist and the savings
    # estimate is mathematically impossible.
    if not isinstance(savings, (int, float)) or not isinstance(cost, (int, float)):
        return True, {"estimated_monthly_savings": savings, "current_monthly_cost": cost, "skipped_reason": "missing_numeric_cost_or_savings"}, "Savings-to-cost comparison skipped because numeric cost data is incomplete."
    ok = savings <= cost
    return ok, {"estimated_monthly_savings": savings, "current_monthly_cost": cost}, "Estimated savings does not exceed relevant current cost."


def _units_currency_consistent(record: NormalizedRecord):
    currency = get(record, "currency")
    resources = get(record, "resources", [])
    resource_currencies = {r.get("currency") for r in resources if isinstance(r, dict) and r.get("currency")}
    ok = exists(currency) and (not resource_currencies or resource_currencies == {currency})
    return ok, {"currency": currency, "resource_currencies": sorted(resource_currencies)}, "Units and currency are consistent."


def _deletion_evidence(record: NormalizedRecord):
    recs = get(record, "recommendations", [])
    bad = []
    for rec in recs if isinstance(recs, list) else []:
        action = str(rec.get("action", "")).lower()
        evidence = str(rec.get("evidence", "")).lower()
        if "delete" in action and not any(term in evidence for term in ["unattached", "zero cpu", "idle 30", "owner approved"]):
            bad.append(rec.get("resource_id"))
    return not bad, {"insufficient_deletion_evidence": bad}, "Deletion is not recommended without sufficient evidence."


def _visual_valid(record: NormalizedRecord):
    chart = get(record, "chart_data")
    if not chart:
        return True, {"present": False}, "Chart or table data is not present and is not required."
    ok = isinstance(chart, dict) and bool(chart.get("columns")) and bool(chart.get("rows"))
    return ok, {"present": True}, "Chart or table data is valid."


def _time_windows_consistent(record: NormalizedRecord):
    period = get(record, "telemetry_period", {})
    try:
        start = datetime.fromisoformat(str(period.get("start")))
        end = datetime.fromisoformat(str(period.get("end")))
        ok = start < end
    except Exception:
        ok = False
    return ok, {"period": period}, "Time windows are consistent."


def _query_relevant(record: NormalizedRecord):
    query = get(record, "user_query")
    answer = get(record, "query_response")
    if not query:
        return True, {"query_present": False}, "No user query is present and query relevance is not required."
    q_terms = {t.lower() for t in str(query).split() if len(t) > 4}
    matches = [t for t in q_terms if t in str(answer).lower()]
    return bool(matches), {"matching_terms": matches}, "Query response is relevant."


def build_finops_rules() -> list[Rule]:
    t = ToolCode.FINOPS
    return [
        Rule("FIN-001", "Scope exists", "Subscription or scope ID is mandatory.", Severity.CRITICAL, t, field_exists("scope_id"), "Subscription or scope ID is missing.", "TELEMETRY_COMPLETENESS"),
        Rule("FIN-002", "Resource ID and type exist", "Resources must identify ID and type.", Severity.CRITICAL, t, _resource_id_type, "Resource ID or type is missing.", "TELEMETRY_COMPLETENESS"),
        Rule("FIN-003", "Telemetry period exists", "Time period is mandatory.", Severity.HIGH, t, _telemetry_period, "Telemetry period is missing.", "TELEMETRY_COMPLETENESS"),
        Rule("FIN-004", "Utilization data exists", "CPU or memory utilization is required.", Severity.CRITICAL, t, _utilization_data, "Relevant utilization data is missing.", "TELEMETRY_COMPLETENESS"),
        Rule("FIN-005", "Cost data when savings claimed", "Cost data is required when savings are claimed.", Severity.HIGH, t, _cost_data_when_savings, "Cost data is missing while savings are claimed.", "COST_DATA"),
        Rule("FIN-006", "Classification has evidence", "Idle or oversized classification must be evidenced.", Severity.HIGH, t, _classification_evidence, "Classification evidence is missing.", "IDLE_RESOURCE"),
        Rule("FIN-007", "Recommendation matches utilization", "Recommendation should match telemetry.", Severity.HIGH, t, _recommendation_matches_utilization, "Recommendation does not match utilization evidence.", "RECOMMENDATION_QUALITY"),
        Rule("FIN-008", "Savings non-negative", "Savings cannot be negative.", Severity.MEDIUM, t, _savings_non_negative, "Estimated savings is missing or negative.", "SAVINGS_ESTIMATE"),
        Rule("FIN-009", "Savings not above cost", "Savings should not exceed current cost.", Severity.CRITICAL, t, _savings_not_exceed_cost, "Estimated savings exceeds current cost.", "SAVINGS_ESTIMATE"),
        Rule("FIN-010", "Currency consistent", "Currency must be consistent.", Severity.MEDIUM, t, _units_currency_consistent, "Units or currency are inconsistent.", "COST_DATA"),
        Rule("FIN-011", "Deletion has evidence", "Deletion recommendation requires strong evidence.", Severity.CRITICAL, t, _deletion_evidence, "Deletion is recommended without sufficient evidence.", "RECOMMENDATION_QUALITY"),
        Rule("FIN-012", "Explanation exists", "Plain-language explanation is required.", Severity.MEDIUM, t, field_exists("explanation"), "Explanation is missing.", "RECOMMENDATION_QUALITY"),
        Rule("FIN-013", "Chart data valid", "Visualization data must be valid if present.", Severity.LOW, t, _visual_valid, "Chart or table data is invalid.", "VISUALIZATION_DATA"),
        Rule("FIN-014", "Time windows consistent", "Start must precede end.", Severity.MEDIUM, t, _time_windows_consistent, "Time windows are inconsistent.", "TELEMETRY_COMPLETENESS"),
        Rule("FIN-015", "Query response relevant", "Query response should address the query.", Severity.LOW, t, _query_relevant, "Query response is not relevant.", "QUERY_RELEVANCE"),
    ]


class FinOpsOptimizationTool(ToolNode):
    tool_code = ToolCode.FINOPS
    agent_code = AgentCode.FINOPS_OPTIMIZATION
    summary = "FinOps underutilization, savings, recommendation, and visualization data were validated."

    def __init__(self) -> None:
        super().__init__(build_finops_rules())
