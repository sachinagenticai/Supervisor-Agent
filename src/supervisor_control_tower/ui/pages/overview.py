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
from supervisor_control_tower.insights import InsightsEngine
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import (
    agent_health_card, kpi, readiness_bar, section_header, verdict_badge, page_caption
)


def render(db: Database) -> None:
    st.title("Overview")
    page_caption(
        "One control plane for your AI agents — validate records, detect drift, "
        "track production readiness, and surface actionable recommendations."
    )

    # ── Load all data in one transaction ─────────────────────────────────────
    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        metrics = repo.dashboard_metrics()
        activity = repo.recent_activity(limit=10)
        agent_health_raw = repo.agent_health_metrics()
        trend_raw = repo.trend_data(days=14)
        dist = repo.verdict_distribution()

    engine = InsightsEngine(None)
    health = _build_health(agent_health_raw)
    readiness = engine.production_readiness_scores(health)

    # ── KPI row ───────────────────────────────────────────────────────────────
    total = int(metrics.get("total_validations") or 0)
    pass_rate = float(metrics.get("pass_rate") or 0)
    fail_rate = float(metrics.get("fail_rate") or 0)
    warn_count = int(metrics.get("warning_count") or 0)
    warn_rate = round(warn_count / total * 100, 1) if total else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi("Total Validations", total)
    with c2:
        kpi("Pass Rate", f"{pass_rate}%", helper="Completed runs that passed")
    with c3:
        kpi("Warning Rate", f"{warn_rate}%", helper="Completed runs with warnings")
    with c4:
        kpi("Fail Rate", f"{fail_rate}%", helper="Completed runs that failed")
    with c5:
        kpi("Agents Monitored", int(metrics.get("agents_supported") or 4))

    st.markdown("---")

    # ── Left column: Agent health + readiness ─────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        section_header("Agent Health")
        cols = st.columns(2)
        agent_codes = list(health.keys())
        for i, code in enumerate(agent_codes):
            with cols[i % 2]:
                agent_health_card(code, health[code])

        st.markdown("")
        section_header("Production Readiness")
        for code, score_data in readiness.items():
            readiness_bar(
                score=score_data["score"],
                color=score_data["color"],
                label=f"{score_data['label']} — {score_data['tier_label']}",
            )

    # ── Right column: Charts ──────────────────────────────────────────────────
    with col_right:
        section_header("Validation Trends · Last 14 Days")
        if trend_raw and _PLOTLY:
            _render_trend_chart(trend_raw)
        elif not _PLOTLY:
            st.info("Install plotly (`pip install plotly`) to see trend charts.")
        else:
            st.info("No validation history yet. Run some validations to see trends.")

        st.markdown("")
        section_header("Verdict Distribution")
        if total > 0 and _PLOTLY:
            _render_donut_chart(dist)
        elif total == 0:
            st.info("No completed validations yet.")

    st.markdown("---")

    # ── Recent Activity ────────────────────────────────────────────────────────
    section_header("Recent Activity")
    if not activity:
        st.info("No validation runs yet. Open **Run Validation** and validate a seeded record.")
        return

    df = pd.DataFrame(activity)
    # Colour-code verdicts
    if "verdict" in df.columns:
        df["verdict"] = df["verdict"].apply(_verdict_html)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_health(agent_health_raw: dict) -> dict:
    """Rebuild health dict from raw metrics (avoids circular call)."""
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
                "color": "#9ca3af", "badge_class": "badge-neutral", "last_run": None,
            }
            continue
        pass_r = int(data.get("pass_count", 0)) / total
        fail_r = int(data.get("fail_count", 0)) / total
        warn_r = int(data.get("warning_count", 0)) / total
        if pass_r >= 0.80:
            status, color, badge = "HEALTHY", "#16a34a", "badge-pass"
        elif pass_r >= 0.50:
            status, color, badge = "AT_RISK", "#f59e0b", "badge-warning"
        else:
            status, color, badge = "CRITICAL", "#dc2626", "badge-fail"
        health[code] = {
            "status": status,
            "pass_rate": round(pass_r * 100, 1),
            "warn_rate": round(warn_r * 100, 1),
            "fail_rate": round(fail_r * 100, 1),
            "total": total,
            "label": AGENT_LABELS[code],
            "lifecycle": AGENT_LIFECYCLE.get(code, "Unknown"),
            "icon": AGENT_ICONS.get(code, "🤖"),
            "color": color, "badge_class": badge,
            "last_run": data.get("last_run"),
        }
    return health


def _render_trend_chart(trend_raw: list[dict]) -> None:
    labels = [d["date"] for d in trend_raw]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="PASS", x=labels, y=[d["pass_count"] for d in trend_raw],
                         marker_color="#15803d", opacity=0.9))
    fig.add_trace(go.Bar(name="WARNING", x=labels, y=[d["warning_count"] for d in trend_raw],
                         marker_color="#b45309", opacity=0.9))
    fig.add_trace(go.Bar(name="FAIL", x=labels, y=[d["fail_count"] for d in trend_raw],
                         marker_color="#b91c1c", opacity=0.9))
    fig.update_layout(
        barmode="stack",
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#606a78"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#eef1f4"),
        uirevision="overview_bar_chart",
    )
    st.plotly_chart(fig, width="stretch", key="overview_bar_chart")


def _render_donut_chart(dist: dict) -> None:
    labels = list(dist.keys())
    values = list(dist.values())
    colors = {"PASS": "#15803d", "WARNING": "#b45309", "FAIL": "#b91c1c"}
    color_list = [colors.get(l, "#9ca3af") for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.6,
        marker_colors=color_list,
        textinfo="percent+label",
        textfont_size=13,
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
        font=dict(family="Inter, sans-serif", color="#606a78"),
        paper_bgcolor="white",
        uirevision="overview_donut_chart",
    )
    st.plotly_chart(fig, width="stretch", key="overview_donut_chart")


def _verdict_html(v: str) -> str:
    return v  # plain text; HTML not supported inside st.dataframe
