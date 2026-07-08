from __future__ import annotations

import json

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from supervisor_control_tower.config import get_settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.insights import InsightsEngine
from supervisor_control_tower.models import AppUser, Severity
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import (
    kpi, render_flow, recommendation_card, section_header, severity_icon,
    verdict_badge, page_caption, TOKENS,
)
from supervisor_control_tower.validation_service import ValidationService


def render(db: Database, user: AppUser) -> None:
    st.title("Run Validation")
    page_caption(
        "Select a stored data record. The Supervisor auto-detects the agent and tool — "
        "no manual routing required."
    )

    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        records = repo.list_active_records()

    if not records:
        st.warning("No active validation records found. Run the seed script first (`python run_all.py`).")
        return

    # ── Record selection ───────────────────────────────────────────────────
    labels = {r.dropdown_label: r.id for r in records}
    selected_label = st.selectbox(
        "Data record",
        list(labels.keys()),
        help="Records are pre-loaded seed data representing real-world agent outputs.",
    )
    comments = st.text_area(
        "Comments / focus area (optional)",
        placeholder="e.g. 'Focus on remediation safety' · 'Check for missing tags' · 'Verify savings estimate'",
        max_chars=500,
    )

    # ── Flow diagram ──────────────────────────────────────────────────────
    with st.expander("How does auto-routing work?", expanded=False):
        st.markdown(
            "The **Supervisor Orchestrator** inspects the record's source system, record type, "
            "metadata keys, and payload keys to deterministically select exactly one tool node. "
            "An LLM fallback is used only when deterministic routing is ambiguous."
        )
        render_flow()

    # ── Run button ────────────────────────────────────────────────────────
    is_running = st.session_state.get("validation_running", False)
    if st.button("Run validation", type="primary", disabled=is_running, use_container_width=True):
        st.session_state.validation_running = True
        with st.spinner("Validating record… (running rules → LLM Judge → synthesis)"):
            try:
                service = ValidationService(get_settings(), db)
                result = service.run_validation(labels[selected_label], comments or None, user)
                st.session_state.last_result = result
                st.session_state.validation_running = False
                st.rerun()
            except Exception as exc:
                st.session_state.validation_running = False
                st.error(f"Validation failed: {exc}")

    if "last_result" in st.session_state:
        _render_result(st.session_state.last_result)


# ── Result renderer ────────────────────────────────────────────────────────

def _render_result(result) -> None:
    verdict = result.final.verdict.value
    confidence = result.final.confidence
    agent_code = result.routing.detected_agent_code.value
    tool_code = result.routing.selected_tool.value

    verdict_color = {"PASS": TOKENS["pass"], "WARNING": TOKENS["warn"], "FAIL": TOKENS["fail"]}.get(verdict, TOKENS["muted"])
    verdict_bg = {"PASS": TOKENS["pass_soft"], "WARNING": TOKENS["warn_soft"], "FAIL": TOKENS["fail_soft"]}.get(verdict, TOKENS["bg"])

    st.markdown("---")

    # ── Hero result card ─────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{verdict_bg}; border:1px solid {TOKENS['border']};
                    border-left:4px solid {verdict_color}; border-radius:12px;
                    padding:22px 24px; margin-bottom:20px;
                    box-shadow:0 1px 3px rgba(16,24,40,.05);">
          <div style="display:flex; align-items:center; gap:18px; flex-wrap:wrap;">
            <div>
              <div style="display:flex; align-items:center; gap:10px;">
                <span style="width:11px; height:11px; border-radius:50%; background:{verdict_color};
                             display:inline-block;"></span>
                <span style="font-size:22px; font-weight:800; color:{verdict_color};
                             letter-spacing:0.02em;">{verdict}</span>
              </div>
              <div style="font-size:13.5px; color:{TOKENS['text']}; max-width:640px; margin-top:8px;
                          line-height:1.5;">{result.final.reason}</div>
            </div>
            <div style="margin-left:auto; text-align:right;">
              <div style="font-size:30px; font-weight:800; color:{verdict_color};">{confidence:.0%}</div>
              <div style="font-size:11px; color:{TOKENS['muted']}; text-transform:uppercase;
                          letter-spacing:0.08em;">Confidence</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Routing + metadata row ────────────────────────────────────────────
    mc1, mc2, mc3, mc4 = st.columns(4)
    _info_card = lambda label, value: st.markdown(
        f"""<div style="background:#fff;border:1px solid #e6e8eb;border-radius:12px;
            padding:14px 16px;margin-bottom:4px;
            box-shadow:0 1px 3px rgba(16,24,40,.05);">
          <div style="font-size:11px;color:#98a1ad;text-transform:uppercase;
               letter-spacing:.05em;font-weight:600;margin-bottom:4px;">{label}</div>
          <div style="font-size:14px;font-weight:700;color:#111827;word-break:break-word;
               line-height:1.35;">{value}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    with mc1:
        _info_card("Detected Agent", agent_code.replace("_", " ").title())
    with mc2:
        _info_card("Tool Used", tool_code.replace("_", " ").replace(" tool", "").title())
    with mc3:
        _info_card("Primary Tag", result.final.primary_tag.replace("_", " ").title())
    with mc4:
        _info_card("Data Completeness", f"{result.final.data_completeness:.0%}")

    # ── LLM Analysis narrative (shown always, below the hero card) ────────
    if result.llm_judgement.analysis:
        st.markdown(
            f"""<div style="background:#f8f9ff;border:1px solid #dde3fb;border-left:4px solid #4f46e5;
                border-radius:12px;padding:16px 20px;margin:12px 0 4px;
                box-shadow:0 1px 3px rgba(16,24,40,.04);">
              <div style="font-size:11px;color:#4f46e5;text-transform:uppercase;letter-spacing:.07em;
                          font-weight:700;margin-bottom:8px;">LLM Deep Analysis</div>
              <div style="font-size:14px;color:#111827;line-height:1.7;">{result.llm_judgement.analysis}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Quality dimensions bar (if available) ─────────────────────────────
    qd = result.llm_judgement.quality_dimensions
    if qd:
        _render_quality_dimensions(qd)

    # ── Export ────────────────────────────────────────────────────────────
    _download_result_json(result, verdict, confidence, agent_code, tool_code)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab_rec, tab_llm, tab_routing, tab_score = st.tabs([
        "Recommendations", "LLM Judge", "Routing", "Scorecard"
    ])

    # ── Tab: Recommendations ──────────────────────────────────────────────
    with tab_rec:
        section_header("What should happen next")
        engine = InsightsEngine(None)
        recs = engine.recommendations_for_run(
            rule_results=result.tool_result.rule_results,
            llm_findings=result.llm_judgement.findings,
            verdict=verdict,
            confidence=confidence,
            agent_code=agent_code,
            llm_recommendations=result.llm_judgement.recommendations or [],
        )
        for text, sev in recs:
            recommendation_card(text, severity=sev)

        if result.tool_result.warnings:
            st.markdown("**Additional warnings:**")
            for w in result.tool_result.warnings:
                st.warning(w)

    # ── Tab: LLM Judge ───────────────────────────────────────────────────
    with tab_llm:
        j = result.llm_judgement
        verdict_val = j.verdict.value if hasattr(j.verdict, "value") else str(j.verdict)
        judge_color = {"PASS": TOKENS["pass"], "WARNING": TOKENS["warn"], "FAIL": TOKENS["fail"]}.get(
            verdict_val, TOKENS["muted"]
        )
        focus_txt = "Addressed" if j.focus_area_addressed else "Not addressed"
        st.markdown(
            f"""
            <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                        border-left:4px solid {judge_color}; border-radius:12px; padding:16px 18px;
                        margin-bottom:16px;">
              <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em;
                          color:{TOKENS['muted']}; margin-bottom:6px;">LLM Judge Verdict</div>
              <div style="font-size:16px; font-weight:700; color:{judge_color}; margin-bottom:8px;">
                {verdict_val} · {j.confidence:.0%} confidence
              </div>
              <div style="color:{TOKENS['text']}; font-size:13.5px; line-height:1.5;">{j.reason}</div>
              <div style="margin-top:10px; font-size:12px; color:{TOKENS['muted']};">
                Focus area: {focus_txt}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if j.findings:
            section_header("LLM Judge Findings")
            _sev_color = {
                "CRITICAL": TOKENS["fail"], "HIGH": "#c2410c", "MEDIUM": TOKENS["warn"],
                "LOW": TOKENS["muted"], "INFO": TOKENS["muted"],
            }
            for f in j.findings:
                sev_val = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                col = _sev_color.get(sev_val, TOKENS["muted"])
                st.markdown(
                    f"""
                    <div style="display:flex; gap:10px; align-items:baseline; padding:8px 0;
                                border-bottom:1px solid {TOKENS['border']};">
                      <span style="font-size:10px; font-weight:700; letter-spacing:0.06em;
                                   color:{col}; background:{TOKENS['bg']}; border:1px solid {TOKENS['border']};
                                   border-radius:5px; padding:2px 7px; white-space:nowrap;">{sev_val}</span>
                      <span style="font-size:12px; color:{TOKENS['muted']}; font-family:monospace;">{f.tag}</span>
                      <span style="font-size:13px; color:{TOKENS['text']};">{f.message}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("No adverse LLM Judge findings.")

    # ── Tab: Routing ─────────────────────────────────────────────────────
    with tab_routing:
        section_header("Orchestrator Routing Decision")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Routing Confidence", f"{result.routing.confidence:.0%}")
            st.markdown(f"**Reason:** {result.routing.reason}")
        with c2:
            st.markdown(f"**Record ID:** `{result.record.record_id}`")
            st.markdown(f"**Source System:** `{result.record.source_system}`")
            st.markdown(f"**Record Type:** `{result.record.record_type}`")
            st.markdown(f"**Run ID:** `{result.run_id}`")
            st.markdown(f"**Completed:** {result.completed_at}")
        render_flow(detected_tool=tool_code.replace("_tool", "").replace("_", " ").title())

    # ── Tab: Scorecard ────────────────────────────────────────────────────
    with tab_score:
        section_header("Confidence Scorecard")
        if _PLOTLY:
            _render_scorecard_gauge(confidence)

        sb = result.final.score_breakdown
        if sb:
            section_header("Score Breakdown")
            rows = []
            for k, v in sb.items():
                label = k.replace("_", " ").title()
                if isinstance(v, float):
                    display = f"{v:.1f}" if v < 10 else f"{v:.0f}"
                else:
                    display = str(v)
                rows.append({"Component": label, "Value": display})
            if rows:
                import pandas as _pd
                st.dataframe(_pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Record complexity profile"):
            profile = result.tool_result.derived_metrics.get("record_profile", {})
            if profile:
                p_rows = [{"Field": k.replace("_", " ").title(), "Value": str(v)} for k, v in profile.items()]
                import pandas as _pd
                st.dataframe(_pd.DataFrame(p_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No profile data available.")


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _download_result_json(result, verdict: str, confidence: float, agent_code: str, tool_code: str) -> None:
    """Render a download button with a portable JSON summary of the run."""
    def _sev(x):
        s = getattr(x, "severity", None)
        return s.value if hasattr(s, "value") else str(s)

    j = result.llm_judgement
    export = {
        "run_id": getattr(result, "run_id", None),
        "completed_at": str(getattr(result, "completed_at", "")),
        "record": {
            "record_id": result.record.record_id,
            "source_system": result.record.source_system,
            "record_type": result.record.record_type,
        },
        "verdict": verdict,
        "confidence": round(float(confidence), 4),
        "reason": result.final.reason,
        "primary_tag": result.final.primary_tag,
        "data_completeness": result.final.data_completeness,
        "routing": {
            "detected_agent": agent_code,
            "selected_tool": tool_code,
            "confidence": result.routing.confidence,
            "reason": result.routing.reason,
        },
        "rule_results": [
            {"code": r.rule_code, "name": r.rule_name, "severity": _sev(r),
             "passed": r.passed, "tag": r.tag, "message": r.message}
            for r in result.tool_result.rule_results
        ],
        "llm_judgement": {
            "verdict": j.verdict.value if hasattr(j.verdict, "value") else str(j.verdict),
            "confidence": j.confidence,
            "reason": j.reason,
            "findings": [
                {"severity": _sev(f), "tag": f.tag, "message": f.message}
                for f in (j.findings or [])
            ],
        },
        "score_breakdown": result.final.score_breakdown,
    }
    st.download_button(
        "Download result (JSON)",
        json.dumps(export, default=str, indent=2).encode("utf-8"),
        file_name=f"validation_{str(getattr(result, 'run_id', 'result'))[:8]}.json",
        mime="application/json",
    )


def _render_quality_dimensions(qd: dict) -> None:
    """Render LLM quality dimension scores as a clean horizontal bar row."""
    _labels = {
        "evidence_quality": "Evidence Quality",
        "completeness": "Completeness",
        "safety": "Safety",
        "accuracy": "Accuracy",
    }
    _color = lambda v: TOKENS["pass"] if v >= 0.75 else TOKENS["warn"] if v >= 0.50 else TOKENS["fail"]
    cols = st.columns(len(qd))
    for col, (key, val) in zip(cols, qd.items()):
        pct = min(100, max(0, float(val) * 100))
        label = _labels.get(key, key.replace("_", " ").title())
        color = _color(float(val))
        col.markdown(
            f"""<div style="background:#fff;border:1px solid #e6e8eb;border-radius:12px;
                padding:12px 14px;box-shadow:0 1px 3px rgba(16,24,40,.04);">
              <div style="font-size:11px;color:#98a1ad;text-transform:uppercase;
                   letter-spacing:.05em;font-weight:600;margin-bottom:6px;">{label}</div>
              <div style="font-size:20px;font-weight:800;color:{color};margin-bottom:6px;">{pct:.0f}%</div>
              <div style="background:#eef1f4;border-radius:999px;height:5px;overflow:hidden;">
                <div style="width:{pct}%;height:5px;background:{color};border-radius:999px;"></div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_severity_pie(failed_rules: list) -> None:
    counts: dict[str, int] = {}
    for r in failed_rules:
        sev = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
        counts[sev] = counts.get(sev, 0) + 1
    colors = {"CRITICAL": "#b91c1c", "HIGH": "#c2410c", "MEDIUM": "#b45309", "LOW": "#606a78", "INFO": "#9aa4b2"}
    fig = go.Figure(go.Pie(
        labels=list(counts.keys()),
        values=list(counts.values()),
        marker_colors=[colors.get(k, "#9aa4b2") for k in counts],
        hole=0.5, textinfo="label+value",
    ))
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=4, b=0), paper_bgcolor="white",
                      showlegend=False, font=dict(family="Inter, sans-serif", color="#606a78"),
                      uirevision="validation_severity_pie")
    st.plotly_chart(fig, width="stretch", key="validation_severity_pie")


def _render_scorecard_gauge(confidence: float) -> None:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(confidence * 100, 1),
        title={"text": "Final Confidence Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#4f46e5"},
            "steps": [
                {"range": [0, 60], "color": "#fef2f2"},
                {"range": [60, 80], "color": "#fffbeb"},
                {"range": [80, 100], "color": "#ecfdf3"},
            ],
            "threshold": {"line": {"color": "#b91c1c", "width": 3}, "thickness": 0.75, "value": 60},
        },
        number={"suffix": "%"},
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=10), paper_bgcolor="white",
                      font=dict(family="Inter, sans-serif", color="#606a78"),
                      uirevision="validation_confidence_gauge")
    st.plotly_chart(fig, width="stretch", key="validation_confidence_gauge")
