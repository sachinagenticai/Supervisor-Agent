"""Agent Status & Production Readiness page.

Shows a dedicated deep-dive for each of the 4 agents:
  - Lifecycle stage and production readiness score
  - Health status with pass/warn/fail breakdown
  - Last validation result
  - What the agent needs to do to advance
"""
from __future__ import annotations

import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from supervisor_control_tower.db import Database
from supervisor_control_tower.insights import (
    InsightsEngine, AGENT_LABELS, AGENT_LIFECYCLE, AGENT_ICONS
)
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import (
    readiness_bar, section_header, recommendation_card,
    page_caption, agent_accent, agent_initials, TOKENS,
)


_LIFECYCLE_DESC = {
    "POC": "Early proof-of-concept. Output schema and core capabilities are being defined.",
    "Development / UAT": "Active development. Core functionality complete; undergoing user acceptance testing.",
    "UAT Testing": "Full UAT underway. Awaiting sign-off before production promotion.",
    "UAT Active": "UAT sign-off received. Production promotion planning in progress.",
    "Production": "Live in production. Continuous monitoring active.",
}

_LIFECYCLE_ORDER = ["POC", "Development / UAT", "UAT Testing", "UAT Active", "Production"]

_ADVANCEMENT_CRITERIA = {
    "PIPELINE_TROUBLESHOOTING": [
        "Achieve ≥ 90% pass rate over ≥ 10 validation runs",
        "Zero CRITICAL rule failures in the last 5 runs",
        "No unsafe shell commands or secret exposure in remediation outputs",
        "RCA must reference log evidence in ≥ 95% of failure records",
        "Internal LLM-as-a-Judge confidence > 0.90 on average",
    ],
    "INFRA_PROVISIONING": [
        "Achieve ≥ 90% pass rate over ≥ 10 validation runs",
        "Zero hardcoded credentials in any generated IaC",
        "100% compliance with naming, tagging, and security baseline policies",
        "All generated resources must match requested resources (no unsanctioned additions)",
        "Approval state must always be recorded before IaC is emitted",
    ],
    "FINOPS_OPTIMIZATION": [
        "Achieve ≥ 90% pass rate over ≥ 8 validation runs",
        "Zero savings estimates exceeding current cost",
        "Deletion recommendations must always include unattached/idle evidence",
        "Currency must be consistent across all resources in a record",
        "Complete telemetry data for the full lookback period",
    ],
    "PROJECT_MANAGEMENT": [
        "Achieve ≥ 85% pass rate over ≥ 8 validation runs",
        "100% of generated stories must have testable acceptance criteria",
        "Sprint summary must align with actual Jira issue statuses",
        "Planning recommendation must never recommend over-commitment",
        "All blockers must reference a Jira ticket or commit as source",
    ],
}


def render(db: Database) -> None:
    st.title("Agent Status & Readiness")
    page_caption(
        "Production readiness scores, lifecycle stages, and advancement criteria for each supervised AI agent."
    )

    # ── Load data ─────────────────────────────────────────────────────────
    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        agent_health_raw = repo.agent_health_metrics()
        rule_stats = repo.rule_failure_stats()
        recent_runs = repo.recent_runs_for_drift(limit=50)

    engine = InsightsEngine(None)
    health = _rebuild_health(agent_health_raw)
    readiness = engine.production_readiness_scores(health)
    recs = engine.generate_agent_recommendations(health, rule_stats)

    total_runs = sum(h.get("total", 0) for h in health.values())

    # ── Overall readiness summary bar ─────────────────────────────────────
    section_header("Overall Production Readiness")
    rc1, rc2, rc3, rc4 = st.columns(4)
    for col, code in zip([rc1, rc2, rc3, rc4], AGENT_LABELS):
        rd = readiness.get(code, {})
        with col:
            accent = agent_accent(code)
            initials = agent_initials(code)
            short_label = AGENT_LABELS[code].replace(" Agent", "").replace("InfraScaling & Cost Optimization", "FinOps")
            col.markdown(
                f"""
                <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                            border-radius:12px; padding:16px 14px; text-align:center; margin-bottom:8px;">
                  <div style="width:34px; height:34px; border-radius:9px; margin:0 auto 8px;
                              background:{accent}1a; color:{accent}; display:flex; align-items:center;
                              justify-content:center; font-weight:800; font-size:13px;
                              letter-spacing:0.03em;">{initials}</div>
                  <div style="font-weight:600; font-size:12px; color:{TOKENS['muted']}; margin-bottom:6px;">{short_label}</div>
                  <div style="font-size:28px; font-weight:800; color:{rd.get('color', TOKENS['muted'])};">
                    {rd.get('score', 0):.0f}<span style="font-size:13px; color:{TOKENS['muted']}; font-weight:600;"> / 100</span>
                  </div>
                  <div style="font-size:11px; margin-top:4px; color:{rd.get('color', TOKENS['muted'])};
                              font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">
                    {rd.get('tier_label', 'No Data')}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if _PLOTLY and total_runs > 0:
        _render_readiness_radar(readiness)

    st.markdown("---")

    # ── Per-agent deep dives ───────────────────────────────────────────────
    agent_codes = list(AGENT_LABELS.keys())
    agent_tabs = st.tabs([
        AGENT_LABELS[c].replace(' Agent', '').replace('InfraScaling & Cost Optimization', 'FinOps')
        for c in agent_codes
    ])

    for tab, code in zip(agent_tabs, agent_codes):
        h = health.get(code, {})
        rd = readiness.get(code, {})
        agent_recs = recs.get(code, [])
        criteria = _ADVANCEMENT_CRITERIA.get(code, [])
        lifecycle = AGENT_LIFECYCLE.get(code, "POC")

        with tab:
            # Header row
            th1, th2 = st.columns([2, 1])
            with th1:
                accent = agent_accent(code)
                initials = agent_initials(code)
                st.markdown(
                    f"""
                    <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                                border-left:4px solid {rd.get('color', TOKENS['muted'])};
                                border-radius:12px; padding:18px; margin-bottom:12px;">
                      <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:40px; height:40px; border-radius:10px; background:{accent}1a;
                                    color:{accent}; display:flex; align-items:center; justify-content:center;
                                    font-weight:800; font-size:14px; letter-spacing:0.03em;">{initials}</div>
                        <div style="font-weight:700; font-size:17px; color:{TOKENS['text']};">{AGENT_LABELS[code]}</div>
                      </div>
                      <div style="font-size:13px; color:{TOKENS['muted']}; margin-top:10px;
                                  line-height:1.5;">{_LIFECYCLE_DESC.get(lifecycle, '')}</div>
                      <div style="margin-top:12px;">
                        <span style="background:{rd.get('color', TOKENS['muted'])}; color:white; border-radius:999px;
                                     padding:4px 12px; font-size:11px; font-weight:700; text-transform:uppercase;
                                     letter-spacing:0.04em;">{rd.get('tier_label', 'No Data')}</span>
                        <span style="margin-left:8px; background:{TOKENS['bg']}; border:1px solid {TOKENS['border']};
                                     border-radius:999px; padding:4px 12px; font-size:12px;
                                     color:{TOKENS['muted']};">{lifecycle}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with th2:
                _render_gauge(rd.get("score", 0), rd.get("color", "#9ca3af"), key=f"gauge_{code}")

            # KPI row
            km1, km2, km3, km4 = st.columns(4)
            km1.metric("Pass Rate", f"{h.get('pass_rate', 0):.0f}%")
            km2.metric("Warning Rate", f"{h.get('warn_rate', 0):.0f}%")
            km3.metric("Fail Rate", f"{h.get('fail_rate', 0):.0f}%")
            km4.metric("Total Validations", h.get("total", 0))

            # Lifecycle pipeline
            section_header("Lifecycle Progress")
            _render_lifecycle_pipeline(lifecycle)

            # Advancement criteria
            section_header("Production Advancement Criteria")
            pass_rate = h.get("pass_rate", 0) / 100.0
            total = h.get("total", 0)
            for criterion in criteria:
                # Simple heuristic to mark criteria as met
                met = False
                if "90% pass rate" in criterion and pass_rate >= 0.90 and total >= 10:
                    met = True
                elif "85% pass rate" in criterion and pass_rate >= 0.85 and total >= 8:
                    met = True
                elif "Zero CRITICAL" in criterion:
                    # Can't check from health alone; show as unknown
                    met = None
                if met is True:
                    dot, label, lc = TOKENS["pass"], "Met", TOKENS["pass"]
                elif met is None:
                    dot, label, lc = TOKENS["muted"], "Manual", TOKENS["muted"]
                else:
                    dot, label, lc = TOKENS["border"], "Pending", TOKENS["muted"]
                st.markdown(
                    f"""
                    <div style="display:flex; align-items:baseline; gap:10px; padding:6px 0;">
                      <span style="width:8px; height:8px; border-radius:50%; background:{dot};
                                   display:inline-block; flex:none;"></span>
                      <span style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;
                                   color:{lc}; min-width:56px;">{label}</span>
                      <span style="font-size:13.5px; color:{TOKENS['text']};">{criterion}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Recommendations
            section_header("Recommendations")
            for rec in agent_recs:
                recommendation_card(rec)

            # Last run info
            last = h.get("last_run")
            if last:
                st.markdown(f"<div class='muted'>Last validation: {str(last)[:16]}</div>", unsafe_allow_html=True)


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _render_gauge(score: float, color: str, key: str = "gauge") -> None:
    if not _PLOTLY:
        st.metric("Readiness Score", f"{score:.0f}/100")
        return
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": "Readiness Score", "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickfont": {"size": 10}},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "white",
            "steps": [
                {"range": [0, 40], "color": "#fef2f2"},
                {"range": [40, 65], "color": "#fffbeb"},
                {"range": [65, 80], "color": "#eff6ff"},
                {"range": [80, 100], "color": "#f0fdf4"},
            ],
        },
        number={"suffix": "/100", "font": {"size": 24}},
    ))
    # uirevision makes the serialised figure JSON unique per agent, preventing
    # Streamlit 1.40+ from raising StreamlitDuplicateElementId when the same
    # chart structure is rendered multiple times on the same page.
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="white", uirevision=key)
    st.plotly_chart(fig, width="stretch", key=key)


def _render_readiness_radar(readiness: dict, key: str = "readiness_radar") -> None:
    categories = [
        AGENT_LABELS[c].replace(" Agent", "").replace("InfraScaling & Cost Optimization", "FinOps")
        for c in AGENT_LABELS
    ]
    scores = [readiness.get(c, {}).get("score", 0) for c in AGENT_LABELS]
    # Close the radar
    categories_closed = categories + [categories[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure(go.Scatterpolar(
        r=scores_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor="rgba(79,70,229,0.13)",
        line=dict(color="#4f46e5", width=2),
        marker=dict(size=7, color="#4f46e5"),
        name="Readiness",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#606a78"),
        showlegend=False,
        uirevision=key,
    )
    st.plotly_chart(fig, width="stretch", key=key)


def _render_lifecycle_pipeline(current: str) -> None:
    stages = _LIFECYCLE_ORDER
    parts = []
    for stage in stages:
        is_current = stage == current
        is_past = _LIFECYCLE_ORDER.index(stage) < _LIFECYCLE_ORDER.index(current)
        if is_current:
            color, bg = "#ffffff", "#4f46e5"
        elif is_past:
            color, bg = "#ffffff", "#15803d"
        else:
            color, bg = "#9aa4b2", "#eef1f4"
        short = stage.replace("Development / UAT", "Dev/UAT").replace("UAT Active", "UAT Active")
        parts.append(
            f'<span style="background:{bg}; color:{color}; border-radius:999px; '
            f'padding:5px 12px; font-size:12px; font-weight:600; margin:2px; '
            f'display:inline-block; white-space:nowrap;">{short}</span>'
        )
        if stage != stages[-1]:
            parts.append('<span style="color:#94a3b8; margin:0 2px;">→</span>')
    st.markdown('<div style="line-height:2.5;">' + "".join(parts) + "</div>", unsafe_allow_html=True)


def _rebuild_health(agent_health_raw: dict) -> dict:
    """Rebuild health dict from raw metrics."""
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
