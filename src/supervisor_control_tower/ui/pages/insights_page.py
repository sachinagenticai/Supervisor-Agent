"""Insights & Drift Detection page.

Shows:
  - Overall drift alerts
  - Per-agent drift analysis
  - Top failing rules heatmap
  - Actionable per-agent recommendations
  - Confidence trend chart
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    import plotly.express as px
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from supervisor_control_tower.db import Database
from supervisor_control_tower.insights import InsightsEngine, AGENT_LABELS, AGENT_ICONS
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import (
    drift_alert, recommendation_card, section_header, page_caption, TOKENS
)


def render(db: Database) -> None:
    st.title("Insights & Drift")
    page_caption(
        "Continuous analysis of validation history. Detects when agent performance is drifting, "
        "surfaces the most-failing rules, and generates actionable recommendations per agent."
    )

    # ── Load data ─────────────────────────────────────────────────────────
    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        agent_health_raw = repo.agent_health_metrics()
        rule_stats = repo.rule_failure_stats()
        recent_runs = repo.recent_runs_for_drift(limit=50)
        trend_raw = repo.trend_data(days=14)

    engine = InsightsEngine(None)
    health = _rebuild_health(agent_health_raw)
    drift = engine.drift_analysis(recent_runs)
    per_agent_drift = engine.per_agent_drift(recent_runs)
    readiness = engine.production_readiness_scores(health)
    recs = engine.generate_agent_recommendations(health, rule_stats)
    top_rules = engine.top_failing_rules(rule_stats, limit=10)
    trends = engine.kpi_trends(trend_raw)

    total_runs = sum(h.get("total", 0) for h in health.values())

    if total_runs == 0:
        st.info(
            "**No validation history yet.** Run some validations from the **Run Validation** page "
            "and come back here to see insights."
        )
        _render_empty_state()
        return

    # ── Overall Drift banner ───────────────────────────────────────────────
    section_header("Overall Drift Detection")
    if drift["has_drift"]:
        for alert in drift["alerts"]:
            drift_alert(alert)
    else:
        st.success(f"No drift detected. {drift['message']}")

    if drift.get("early_fail_rate") is not None:
        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Early Fail Rate", f"{drift['early_fail_rate']}%")
        dc2.metric("Recent Fail Rate", f"{drift['recent_fail_rate']}%",
                   delta=f"{drift['recent_fail_rate'] - drift['early_fail_rate']:.1f}%")
        dc3.metric("Early Avg Confidence", f"{drift.get('early_confidence', 0):.3f}")
        dc4.metric("Recent Avg Confidence", f"{drift.get('recent_confidence', 0):.3f}",
                   delta=f"{(drift.get('recent_confidence',0) - drift.get('early_confidence',0)):.3f}")

    st.markdown("---")

    # ── Confidence trend chart ─────────────────────────────────────────────
    if trends["labels"] and _PLOTLY:
        section_header("Confidence & Verdict Trend")
        col_trend, col_conf = st.columns(2)
        with col_trend:
            _render_stacked_trend(trends)
        with col_conf:
            _render_confidence_line(trends)
    elif not _PLOTLY:
        st.warning("Install plotly to see trend charts: `pip install plotly`")

    st.markdown("---")

    # ── Per-agent insights ────────────────────────────────────────────────
    section_header("Per-Agent Analysis")

    agent_tabs = st.tabs([
        AGENT_LABELS.get(code, code).split(' Agent')[0]
        for code in AGENT_LABELS
    ])

    for tab, code in zip(agent_tabs, AGENT_LABELS):
        h = health.get(code, {})
        ad = per_agent_drift.get(code, {})
        agent_recs = recs.get(code, [])
        rd = readiness.get(code, {})

        with tab:
            # Agent header
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Pass Rate", f"{h.get('pass_rate', 0):.0f}%")
            tc2.metric("Fail Rate", f"{h.get('fail_rate', 0):.0f}%")
            tc3.metric("Total Runs", h.get("total", 0))
            tc4.metric("Readiness Score", f"{rd.get('score', 0):.0f}/100")

            # Drift
            if ad.get("has_drift"):
                st.markdown("**Drift Alerts:**")
                for alert in ad.get("alerts", []):
                    drift_alert(alert)
            elif h.get("total", 0) >= 4:
                st.success("No drift detected for this agent.")
            else:
                st.info(f"Need ≥ 4 runs for drift analysis (have {h.get('total',0)}).")

            # Recommendations
            st.markdown("**Recommendations:**")
            for rec in agent_recs:
                recommendation_card(rec)

            # Agent-level failing rules
            agent_rules = [r for r in rule_stats if r.get("agent_code") == code and r.get("fail_count", 0) > 0]
            if agent_rules:
                st.markdown("**Rule failures for this agent:**")
                rdf = pd.DataFrame(agent_rules)[["rule_code", "rule_name", "fail_count", "total", "fail_rate", "tag"]]
                rdf.columns = ["Code", "Rule", "Fails", "Total", "Fail %", "Tag"]
                st.dataframe(rdf, use_container_width=True, hide_index=True, height=200)

    st.markdown("---")

    # ── Top Failing Rules across all agents ───────────────────────────────
    section_header("Top Failing Rules · All Agents")
    if top_rules:
        tdf = pd.DataFrame(top_rules)[["rule_code", "rule_name", "agent_code", "fail_count", "total", "fail_rate", "tag"]]
        tdf.columns = ["Code", "Rule Name", "Agent", "Fails", "Total", "Fail %", "Tag"]
        tdf["Agent"] = tdf["Agent"].str.replace("_", " ").str.title()

        if _PLOTLY:
            _render_rules_heatmap(tdf)
        st.dataframe(tdf, use_container_width=True, hide_index=True)
    else:
        st.success("No rule failures recorded yet.")

    st.markdown("---")

    # ── Production readiness summary table ───────────────────────────────
    section_header("Production Readiness Summary")
    rd_rows = []
    for code, rd in readiness.items():
        rd_rows.append({
            "Agent": rd.get("label", code),
            "Lifecycle Stage": rd.get("lifecycle", ""),
            "Pass Rate": f"{rd.get('pass_rate', 0):.0f}%",
            "Validations": rd.get("total", 0),
            "Readiness Score": f"{rd.get('score', 0):.0f}/100",
            "Tier": rd.get("tier_label", ""),
            "Prod Ready": "Yes" if rd.get("production_ready") else "No",
        })
    rd_df = pd.DataFrame(rd_rows)
    st.dataframe(rd_df, use_container_width=True, hide_index=True)


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _render_stacked_trend(trends: dict) -> None:
    fig = go.Figure()
    fig.add_trace(go.Bar(name="PASS", x=trends["labels"], y=trends["pass"],
                         marker_color="#15803d", opacity=0.9))
    fig.add_trace(go.Bar(name="WARNING", x=trends["labels"], y=trends["warning"],
                         marker_color="#b45309", opacity=0.9))
    fig.add_trace(go.Bar(name="FAIL", x=trends["labels"], y=trends["fail"],
                         marker_color="#b91c1c", opacity=0.9))
    fig.update_layout(
        barmode="stack", height=240,
        margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#606a78"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#eef1f4"),
        uirevision="insights_stacked_bar",
    )
    st.plotly_chart(fig, width="stretch", key="insights_stacked_bar")


def _render_confidence_line(trends: dict) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trends["labels"], y=trends["confidence"],
        mode="lines+markers",
        line=dict(color="#4f46e5", width=2),
        marker=dict(size=6, color="#4f46e5"),
        fill="tozeroy", fillcolor="rgba(79,70,229,0.08)",
        name="Avg Confidence",
    ))
    fig.add_hline(y=0.80, line_dash="dot", line_color="#b45309", annotation_text="High threshold (0.80)")
    fig.add_hline(y=0.60, line_dash="dot", line_color="#b91c1c", annotation_text="Min threshold (0.60)")
    fig.update_layout(
        height=240, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#606a78"),
        yaxis=dict(range=[0, 1.05], gridcolor="#eef1f4"),
        xaxis=dict(showgrid=False),
        showlegend=False,
        uirevision="insights_confidence_line",
    )
    st.plotly_chart(fig, width="stretch", key="insights_confidence_line")


def _render_rules_heatmap(tdf: pd.DataFrame) -> None:
    fig = px.bar(
        tdf.head(10), x="Fails", y="Rule Name",
        color="Fail %", color_continuous_scale="OrRd",
        orientation="h", height=280,
        text="Fails",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#606a78"),
        xaxis_title="Failure count", yaxis_title="",
        uirevision="insights_rules_heatmap",
    )
    st.plotly_chart(fig, width="stretch", key="insights_rules_heatmap")


def _render_empty_state() -> None:
    st.markdown(
        """
        ### What you'll see after running validations:
        - **Drift alerts** — automatically flagged if failure rate spikes
        - **Per-agent analysis** — pass/fail rate, top failing rules, lifecycle guidance
        - **Actionable recommendations** — specific fixes for the agent engineering team
        - **Trend charts** — confidence and verdict distribution over time
        - **Production readiness scores** — 0–100 score per agent
        """
    )


def _rebuild_health(agent_health_raw: dict) -> dict:
    """Rebuild health dict from raw metrics."""
    from supervisor_control_tower.insights import AGENT_LABELS, AGENT_LIFECYCLE, AGENT_ICONS
    health = {}
    for code in AGENT_LABELS:
        data = agent_health_raw.get(code, {})
        total = int(data.get("total", 0))
        if total == 0:
            health[code] = {
                "status": "NO_DATA", "pass_rate": 0.0, "warn_rate": 0.0,
                "fail_rate": 0.0, "total": 0,
                "label": AGENT_LABELS[code],
                "lifecycle": AGENT_LIFECYCLE.get(code, "Unknown"),
                "icon": AGENT_ICONS.get(code, "🤖"),
                "color": "#9ca3af", "last_run": None,
            }
            continue
        pass_r = int(data.get("pass_count", 0)) / total
        fail_r = int(data.get("fail_count", 0)) / total
        warn_r = int(data.get("warning_count", 0)) / total
        color = "#15803d" if pass_r >= 0.80 else "#b45309" if pass_r >= 0.50 else "#b91c1c"
        status = "HEALTHY" if pass_r >= 0.80 else "AT_RISK" if pass_r >= 0.50 else "CRITICAL"
        health[code] = {
            "status": status,
            "pass_rate": round(pass_r * 100, 1),
            "warn_rate": round(warn_r * 100, 1),
            "fail_rate": round(fail_r * 100, 1),
            "total": total, "color": color,
            "label": AGENT_LABELS[code],
            "lifecycle": AGENT_LIFECYCLE.get(code, "Unknown"),
            "icon": AGENT_ICONS.get(code, "🤖"),
            "last_run": data.get("last_run"),
        }
    return health
