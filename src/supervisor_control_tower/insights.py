"""Insights, drift detection, recommendations, and production readiness engine.

This module is the analytical brain of the Supervisor Agent Control Tower.
It reads historical validation data and produces:
  - Per-agent health summaries
  - Drift alerts (when failure rates change significantly)
  - Production readiness scores
  - Actionable per-agent and per-run recommendations
  - KPI trend data for charting
"""
from __future__ import annotations

from typing import Any


# ── Agent metadata ──────────────────────────────────────────────────────────

AGENT_LABELS: dict[str, str] = {
    "PIPELINE_TROUBLESHOOTING": "Pipeline Troubleshooting Agent",
    "INFRA_PROVISIONING": "Infrastructure Provisioning Agent",
    "FINOPS_OPTIMIZATION": "InfraScaling & Cost Optimization Agent",
    "PROJECT_MANAGEMENT": "AI-Driven Project Management Agent",
}

AGENT_LIFECYCLE: dict[str, str] = {
    "PIPELINE_TROUBLESHOOTING": "UAT Testing",
    "INFRA_PROVISIONING": "Development / UAT",
    "FINOPS_OPTIMIZATION": "UAT Active",
    "PROJECT_MANAGEMENT": "POC",
}

AGENT_ICONS: dict[str, str] = {
    "PIPELINE_TROUBLESHOOTING": "🔧",
    "INFRA_PROVISIONING": "☁️",
    "FINOPS_OPTIMIZATION": "💰",
    "PROJECT_MANAGEMENT": "📋",
}

# ── Rule-level actionable fix hints ─────────────────────────────────────────

_RULE_FIX: dict[str, str] = {
    # Pipeline rules
    "PIPE-001": "Agent must always include `pipeline_run_id` in its output. Verify the webhook payload schema.",
    "PIPE-002": "Output `source_system` must be one of: github_actions, azure_devops, jenkins. Check agent connector config.",
    "PIPE-003": "Failed status field is missing. Agent should always emit the pipeline status code.",
    "PIPE-004": "Agent must identify the `failed_stage`. Check the log-parsing module.",
    "PIPE-005": "Log evidence or stack trace must be captured. Ensure the agent's log-capture connector is active.",
    "PIPE-006": "RCA is required for every failure. Check the agent's RCA generation module.",
    "PIPE-007": "RCA must reference specific tokens from the captured logs. Improve evidence-linking in the RCA prompt.",
    "PIPE-008": "A remediation recommendation is required. The agent's fix-generation step may have failed or been skipped.",
    "PIPE-009": "The proposed change must identify a target file or config path. Tighten the PR-generation prompt.",
    "PIPE-010": "Secret or credential detected in payload. Immediately update the agent's log-scrubbing module.",
    "PIPE-011": "Unsafe shell command (e.g. rm -rf /) detected in remediation. Block dangerous commands in agent output filter.",
    "PIPE-012": "Agent confidence score is missing or outside 0–1. Normalise confidence before writing output.",
    "PIPE-013": "PR metadata is incomplete. Ensure title, branch, and files_changed are always emitted.",
    "PIPE-014": "Post-fix outcome is inconsistent. Validate outcome status values in the agent's rerun-check module.",
    "PIPE-015": "Notification output is missing. Check the Teams/alert dispatch step in the agent pipeline.",
    "PIPE-016": "Repository context (name, branch, commit, timestamp) is incomplete. Verify source metadata extraction.",
    # Infrastructure rules
    "INFRA-001": "Target environment is invalid. Use only: dev, test, uat, staging, prod.",
    "INFRA-002": "Requested resource types must all appear in interpreted_resources.",
    "INFRA-003": "Generated IaC is missing. The IaC-generation module may have failed.",
    "INFRA-004": "IaC language must be terraform or bicep. Set the language explicitly in the agent config.",
    "INFRA-005": "Naming conventions failed. Apply the corporate naming policy template before emitting IaC.",
    "INFRA-006": "Required tags are missing. Enforce tags: app, owner, environment, cost_center in the tagging module.",
    "INFRA-007": "Environment names are mixed in the generated IaC. Use environment-specific variable files.",
    "INFRA-008": "Security baseline fields are incomplete (private_network, encryption, rbac). Fill from the security manifest.",
    "INFRA-009": "Approval state is missing when approval_required=true. Do not emit output before approval is recorded.",
    "INFRA-010": "Plan and IaC are inconsistent. Verify that all interpreted_resources appear in generated_iac.",
    "INFRA-011": "A requested resource is absent from the generated IaC. Review resource-mapping logic.",
    "INFRA-012": "An unapproved resource was added. Only add resources listed in approved_additional_resources.",
    "INFRA-013": "Hardcoded credentials detected in IaC. Require Key Vault references; block plaintext secrets.",
    # FinOps rules
    "FIN-001": "scope_id (subscription/resource group) is required. Check the Azure Cost Management connector.",
    "FIN-002": "Each resource must have resource_id and resource_type. Validate the telemetry export schema.",
    "FIN-003": "Telemetry period (start/end) is required. Ensure the lookback window is always recorded.",
    "FIN-004": "Utilisation data (CPU/memory) is missing. Verify Azure Monitor metrics are being fetched.",
    "FIN-005": "current_monthly_cost is required when savings are claimed. Pull cost data before making estimates.",
    "FIN-006": "Idle/oversized classification must be backed by utilisation evidence. Do not classify without data.",
    "FIN-007": "Recommendation action does not match the utilisation pattern. Validate action–classification mapping.",
    "FIN-008": "Savings estimate is negative or missing. Recalculate and ensure the value is non-negative.",
    "FIN-009": "Savings exceed the current cost — mathematically impossible. Recheck the savings formula.",
    "FIN-010": "Currency is inconsistent across resources. Normalise all values to a single currency.",
    "FIN-011": "Deletion recommended without sufficient evidence. Require 'unattached' or 'zero-cpu' evidence tag.",
    "FIN-012": "Plain-language explanation is missing. Add an explanation field to every analysis record.",
    "FIN-013": "Chart data structure is invalid (columns/rows). Fix the chart-data serialisation step.",
    "FIN-014": "Telemetry start is after end. Swap period values or fix the date-range parameter.",
    "FIN-015": "Query response does not address the user query. Improve the FinOps Copilot prompt.",
    # Project Management rules
    "PM-001": "Sprint ID and goal are required when sprint_required=true. Ensure Jira sprint data is fetched.",
    "PM-002": "Acceptance criteria must use testable language (Given/When/Then). Update the story-generation prompt.",
    "PM-003": "Sprint summary does not reflect issue statuses. Re-sync status from Jira before emitting summary.",
    "PM-004": "PR and deployment statuses are not represented in the sprint summary. Add repo-activity parsing.",
    "PM-005": "Blockers lack source evidence. Each blocker must reference a Jira ticket or commit.",
    "PM-006": "Velocity is missing or non-positive. Pull velocity from Jira sprint history.",
    "PM-007": "Duplicate story detected — identical title exists in backlog. Add a deduplication check.",
    "PM-008": "Overcommitment: recommended_points exceeds available_points. Check capacity calculation.",
    "PM-009": "Planning recommendation is missing. The planning-recommendation step may have been skipped.",
    "PM-010": "Completed work is not reflected in repo activity. Align repo_activity with Jira completed items.",
    "PM-011": "Risks lack date evidence. Attach a date_evidence field to each risk entry.",
}


# ── InsightsEngine ───────────────────────────────────────────────────────────

class InsightsEngine:
    """Reads historical repository data and produces analytical insights."""

    def __init__(self, repo: Any) -> None:
        self.repo = repo

    # ---- Agent Health -------------------------------------------------------

    def agent_health_summary(self) -> dict[str, dict[str, Any]]:
        """Health status per agent based on all completed validation runs."""
        try:
            metrics: dict[str, Any] = self.repo.agent_health_metrics()
        except Exception:
            metrics = {}

        health: dict[str, dict[str, Any]] = {}
        for code in AGENT_LABELS:
            data = metrics.get(code, {})
            total = int(data.get("total", 0))
            if total == 0:
                health[code] = {
                    "status": "NO_DATA",
                    "pass_rate": 0.0,
                    "warn_rate": 0.0,
                    "fail_rate": 0.0,
                    "total": 0,
                    "label": AGENT_LABELS[code],
                    "lifecycle": AGENT_LIFECYCLE.get(code, "Unknown"),
                    "icon": AGENT_ICONS.get(code, "🤖"),
                    "color": "#9ca3af",
                    "badge_class": "badge-neutral",
                    "last_run": None,
                }
                continue
            pass_rate = int(data.get("pass_count", 0)) / total
            fail_rate = int(data.get("fail_count", 0)) / total
            warn_rate = int(data.get("warning_count", 0)) / total

            if pass_rate >= 0.80:
                status, color, badge = "HEALTHY", "#16a34a", "badge-pass"
            elif pass_rate >= 0.50:
                status, color, badge = "AT_RISK", "#f59e0b", "badge-warning"
            else:
                status, color, badge = "CRITICAL", "#dc2626", "badge-fail"

            health[code] = {
                "status": status,
                "pass_rate": round(pass_rate * 100, 1),
                "warn_rate": round(warn_rate * 100, 1),
                "fail_rate": round(fail_rate * 100, 1),
                "total": total,
                "label": AGENT_LABELS[code],
                "lifecycle": AGENT_LIFECYCLE.get(code, "Unknown"),
                "icon": AGENT_ICONS.get(code, "🤖"),
                "color": color,
                "badge_class": badge,
                "last_run": data.get("last_run"),
            }
        return health

    # ---- Drift Detection ----------------------------------------------------

    def drift_analysis(self, recent_runs: list[dict[str, Any]]) -> dict[str, Any]:
        """Compare earliest and latest halves of run history to detect drift."""
        completed = [r for r in recent_runs if r.get("execution_status") == "COMPLETED"]
        if len(completed) < 4:
            return {
                "has_drift": False,
                "alerts": [],
                "message": "Insufficient history for drift analysis (need ≥ 4 completed runs).",
                "early_fail_rate": None,
                "recent_fail_rate": None,
                "early_confidence": None,
                "recent_confidence": None,
            }

        mid = len(completed) // 2
        early = completed[mid:]   # older half
        recent = completed[:mid]  # newer half

        def fail_rate(runs: list[dict]) -> float:
            return sum(1 for r in runs if r.get("final_verdict") == "FAIL") / len(runs) if runs else 0.0

        def avg_conf(runs: list[dict]) -> float:
            vals = [float(r["final_confidence"]) for r in runs if r.get("final_confidence") is not None]
            return sum(vals) / len(vals) if vals else 0.0

        ef, rf = fail_rate(early), fail_rate(recent)
        ec, rc = avg_conf(early), avg_conf(recent)
        drift = rf - ef
        conf_drop = ec - rc

        alerts: list[dict[str, str]] = []
        if drift >= 0.25:
            alerts.append({
                "severity": "HIGH",
                "icon": "🔴",
                "message": f"Failure rate surged +{drift*100:.0f}% in recent runs vs earlier period.",
                "action": "Investigate which rules are newly failing. Check if agent output schemas changed.",
            })
        elif drift >= 0.10:
            alerts.append({
                "severity": "MEDIUM",
                "icon": "🟡",
                "message": f"Failure rate rose +{drift*100:.0f}% in recent runs.",
                "action": "Monitor closely. Review agent changelogs and new record types.",
            })
        elif drift <= -0.15:
            alerts.append({
                "severity": "LOW",
                "icon": "🟢",
                "message": f"Failure rate improved by {abs(drift)*100:.0f}% — positive drift detected.",
                "action": "Confirm fixes are intentional and update production readiness assessment.",
            })

        if conf_drop >= 0.12:
            alerts.append({
                "severity": "MEDIUM",
                "icon": "🟡",
                "message": f"Average confidence dropped {conf_drop:.2f} in recent runs.",
                "action": "Degraded confidence may indicate payload quality issues or model instability.",
            })

        return {
            "has_drift": bool(alerts),
            "alerts": alerts,
            "message": f"Analysed {len(completed)} completed runs ({mid} recent, {len(early)} earlier).",
            "early_fail_rate": round(ef * 100, 1),
            "recent_fail_rate": round(rf * 100, 1),
            "early_confidence": round(ec, 3),
            "recent_confidence": round(rc, 3),
        }

    # ---- Agent-level Drift --------------------------------------------------

    def per_agent_drift(self, recent_runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Drift analysis broken down per agent."""
        result: dict[str, dict[str, Any]] = {}
        for code in AGENT_LABELS:
            agent_runs = [r for r in recent_runs if r.get("detected_agent_code") == code]
            result[code] = self.drift_analysis(agent_runs)
        return result

    # ---- Production Readiness -----------------------------------------------

    def production_readiness_scores(self, agent_health: dict[str, dict]) -> dict[str, dict[str, Any]]:
        """Calculate a 0–100 production readiness score per agent."""
        scores: dict[str, dict[str, Any]] = {}
        for code, health in agent_health.items():
            total = health.get("total", 0)
            pass_pct = health.get("pass_rate", 0.0) / 100.0

            if total == 0:
                scores[code] = {
                    "score": 0, "tier": "NO_DATA", "color": "#9aa4b2",
                    "production_ready": False, "label": health.get("label", code),
                    "lifecycle": health.get("lifecycle", ""), "pass_rate": 0, "total": 0,
                    "tier_label": "No Data Yet",
                }
                continue

            # Base score from pass rate (0-70 pts)
            base = pass_pct * 70.0
            # Volume bonus: max +10 for ≥10 runs
            volume_bonus = min(10.0, total * 1.0)
            # Lifecycle bonus (0-20)
            lifecycle_bonus = {
                "UAT Active": 20.0,
                "UAT Testing": 15.0,
                "Development / UAT": 10.0,
                "POC": 5.0,
            }.get(health.get("lifecycle", ""), 0.0)

            raw = base + volume_bonus + lifecycle_bonus
            score = round(min(100.0, raw), 1)

            if score >= 80 and pass_pct >= 0.90:
                tier, color, tier_label, ready = "PRODUCTION_READY", "#15803d", "Production Ready", True
            elif score >= 65 or pass_pct >= 0.70:
                tier, color, tier_label, ready = "UAT_READY", "#4f46e5", "UAT Ready", False
            elif score >= 45:
                tier, color, tier_label, ready = "DEVELOPMENT", "#b45309", "Development / Testing", False
            else:
                tier, color, tier_label, ready = "NEEDS_IMPROVEMENT", "#b91c1c", "Needs Improvement", False

            scores[code] = {
                "score": score,
                "tier": tier,
                "color": color,
                "production_ready": ready,
                "label": health.get("label", code),
                "lifecycle": health.get("lifecycle", ""),
                "pass_rate": health.get("pass_rate", 0.0),
                "total": total,
                "tier_label": tier_label,
            }
        return scores

    # ---- Top Failing Rules --------------------------------------------------

    def top_failing_rules(self, rule_stats: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        """Top N rules sorted by absolute failure count."""
        return sorted(rule_stats, key=lambda r: r.get("fail_count", 0), reverse=True)[:limit]

    # ---- Agent Recommendations ----------------------------------------------

    def generate_agent_recommendations(
        self,
        agent_health: dict[str, dict],
        rule_stats: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Produce per-agent actionable recommendations based on observed patterns."""
        # Index rule failure counts by agent
        agent_rule_failures: dict[str, list[dict]] = {}
        for r in rule_stats:
            agent_code = r.get("agent_code", "")
            if r.get("fail_count", 0) > 0 and agent_code:
                agent_rule_failures.setdefault(agent_code, []).append(r)

        recommendations: dict[str, list[str]] = {}
        for code, health in agent_health.items():
            recs: list[str] = []
            total = health.get("total", 0)
            fail_pct = health.get("fail_rate", 0.0)
            pass_pct = health.get("pass_rate", 0.0)
            lifecycle = health.get("lifecycle", "")

            if total == 0:
                recs.append("No validation runs recorded yet. Run at least one validation to unlock recommendations.")
                recommendations[code] = recs
                continue

            # Overall verdict guidance
            if fail_pct >= 50:
                recs.append(f"Critical: {fail_pct:.0f}% failure rate. Block promotion and escalate to the agent engineering team.")
            elif fail_pct >= 25:
                recs.append(f"High failure rate ({fail_pct:.0f}%). Do not promote until root causes are fixed.")
            elif pass_pct >= 90 and total >= 5:
                recs.append(f"Strong track record ({pass_pct:.0f}% pass rate over {total} runs). Consider advancing lifecycle stage.")

            # Top failing rule
            failing = sorted(agent_rule_failures.get(code, []), key=lambda r: r.get("fail_count", 0), reverse=True)
            if failing:
                top = failing[0]
                fix = _RULE_FIX.get(top.get("rule_code", ""), "Review the failing rule in the agent output.")
                recs.append(
                    f"Most-failing rule: **{top.get('rule_name', 'Unknown')}** "
                    f"({top.get('fail_count', 0)} failures, tag: {top.get('tag', '')}). Fix: {fix}"
                )

            # Lifecycle-specific guidance
            if lifecycle == "POC":
                recs.append("POC stage: Focus on defining output schema and required fields. Run at least 10 validations before advancing.")
            elif lifecycle in ("Development / UAT", "UAT Testing"):
                recs.append("UAT stage: Achieve ≥ 80% pass rate over ≥ 5 runs before planning production promotion.")
            elif lifecycle == "UAT Active":
                recs.append("UAT Active: If pass rate > 90%, initiate production readiness review with the governance board.")

            # Agent-specific deep tips
            if code == "PIPELINE_TROUBLESHOOTING":
                safety_fails = [r for r in failing if r.get("tag") in ("REMEDIATION_SAFETY",)]
                if safety_fails:
                    recs.append("Remediation safety violations detected. Add an output filter that blocks `rm -rf`, `chmod 777`, and exposed secrets.")
                rca_fails = [r for r in failing if "RCA" in r.get("tag", "")]
                if rca_fails:
                    recs.append("RCA quality is below standard. Ensure the agent cites specific log tokens when generating root cause analysis.")

            elif code == "INFRA_PROVISIONING":
                sec_fails = [r for r in failing if "SECURITY" in r.get("tag", "") or "CREDENTIAL" in r.get("tag", "")]
                if sec_fails:
                    recs.append("Security baseline violations. All IaC must use Key Vault references — hardcoded secrets are a CRITICAL blocker.")
                tag_fails = [r for r in failing if "TAG" in r.get("tag", "") or "NAMING" in r.get("tag", "")]
                if tag_fails:
                    recs.append("Naming / tagging policy violations. Apply the corporate naming module to all generated resources.")

            elif code == "FINOPS_OPTIMIZATION":
                savings_fails = [r for r in failing if "SAVINGS" in r.get("tag", "")]
                if savings_fails:
                    recs.append("Savings estimate errors. Validate: savings ≥ 0 and savings ≤ current_cost before emitting recommendations.")
                tele_fails = [r for r in failing if "TELEMETRY" in r.get("tag", "")]
                if tele_fails:
                    recs.append("Telemetry data is incomplete. Ensure Azure Monitor metrics are fetched for the full lookback period.")

            elif code == "PROJECT_MANAGEMENT":
                ac_fails = [r for r in failing if "CRITERIA" in r.get("tag", "") or "ACCEPTANCE" in r.get("tag", "")]
                if ac_fails:
                    recs.append("Acceptance criteria quality issues. Update the story-generation prompt to enforce Given/When/Then format.")
                sprint_fails = [r for r in failing if "SPRINT" in r.get("tag", "")]
                if sprint_fails:
                    recs.append("Sprint consistency failures. Re-fetch Jira issue statuses before generating the sprint summary.")

            if not recs:
                recs.append("Agent performance looks good. Continue monitoring for drift.")

            recommendations[code] = recs

        return recommendations

    # ---- Run-level Recommendations ------------------------------------------

    def recommendations_for_run(
        self,
        rule_results: list[Any],
        llm_findings: list[Any],
        verdict: str,
        confidence: float,
        agent_code: str,
        llm_recommendations: list[dict] | None = None,
    ) -> list[tuple[str, str]]:
        """Return list of (text, severity) tuples — one actionable item per finding.

        If the LLM returned structured recommendations, those are used as the primary
        source. Rule-based fallbacks are used only when LLM recs are unavailable.
        Items are sorted most-severe first. Text is always plain English — no raw
        codes, no underscores, no bold-header patterns.
        """
        _SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "PASS": 5, "": 6}
        items: list[tuple[str, str]] = []

        # ── LLM-generated recommendations (primary) ───────────────────────
        # These are the LLM's own plain-English action items — show as-is.
        if llm_recommendations:
            priority_map = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
            for rec in llm_recommendations:
                priority = str(rec.get("priority", "MEDIUM")).upper()
                sev = priority_map.get(priority, "MEDIUM")
                action = str(rec.get("action", "")).strip()
                if action:
                    items.append((action, sev))

        # ── LLM Judge findings (observation context) ──────────────────────
        # Show the message only — no raw tag code, no bold header pattern.
        for finding in (llm_findings or []):
            sev_val = getattr(getattr(finding, "severity", None), "value", "INFO").upper()
            msg = str(getattr(finding, "message", "")).strip()
            if msg:
                items.append((msg, sev_val))

        # ── Rule-based fallbacks (only if LLM recs unavailable) ──────────
        if not llm_recommendations:
            failed_rules = [r for r in rule_results if not getattr(r, "passed", True)]
            failed_rules.sort(
                key=lambda r: _SEV_ORDER.get(
                    getattr(getattr(r, "severity", None), "value", "INFO").upper(), 6
                )
            )
            for rule in failed_rules:
                code = getattr(rule, "rule_code", "")
                sev = getattr(rule, "severity", None)
                sev_val = (sev.value if hasattr(sev, "value") else str(sev)).upper()
                fix = _RULE_FIX.get(code) or getattr(rule, "message", "")
                if fix:
                    items.append((fix, sev_val))

        # Sort all items by severity
        items.sort(key=lambda x: _SEV_ORDER.get(x[1], 6))

        # ── Overall verdict summary ───────────────────────────────────────
        if verdict == "PASS" and confidence >= 0.90:
            items.append((
                "All checks passed with high confidence. "
                "This output meets all validation standards and is a strong candidate for regression testing baseline.",
                "PASS",
            ))
        elif verdict == "PASS":
            items.append((
                "Validation passed. "
                "Continue monitoring for drift and re-validate after any agent updates.",
                "INFO",
            ))
        elif verdict == "WARNING":
            items.append((
                "Human review is recommended before promoting this agent to the next lifecycle stage. "
                "A senior engineer should review the findings above.",
                "MEDIUM",
            ))
        elif verdict == "FAIL":
            items.append((
                "Do not promote this agent version. "
                "Resolve all issues listed above, re-run the validation suite, and obtain a PASS verdict before advancing.",
                "CRITICAL",
            ))

        if not items:
            items.append(("No issues detected. Agent output meets all validation standards.", "PASS"))

        return items

    # ---- KPI Trends ---------------------------------------------------------

    def kpi_trends(self, trend_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Process daily trend data for Plotly/chart rendering."""
        if not trend_data:
            return {"labels": [], "pass": [], "warning": [], "fail": [], "confidence": [], "total": []}
        return {
            "labels": [str(d.get("date", "")) for d in trend_data],
            "pass": [int(d.get("pass_count", 0)) for d in trend_data],
            "warning": [int(d.get("warning_count", 0)) for d in trend_data],
            "fail": [int(d.get("fail_count", 0)) for d in trend_data],
            "total": [int(d.get("total", 0)) for d in trend_data],
            "confidence": [round(float(d.get("avg_confidence", 0) or 0), 3) for d in trend_data],
        }
