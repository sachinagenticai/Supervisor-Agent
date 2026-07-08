from __future__ import annotations

from typing import Any

import streamlit as st

from supervisor_control_tower.models import Verdict


# ── Design tokens ────────────────────────────────────────────────────────────
# A single source of truth for the visual language. Change these to re-theme
# the entire application (e.g. to align with a corporate brand palette).

TOKENS = {
    "bg":            "#f6f7f9",   # app canvas
    "surface":       "#ffffff",   # cards / panels
    "surface_2":     "#fafbfc",   # subtle inset panels
    "border":        "#e6e8eb",   # hairline borders
    "border_strong": "#d4d7dc",
    "text":          "#111827",   # near-black headings
    "text_muted":    "#606a78",   # secondary text
    "text_subtle":   "#98a1ad",   # tertiary / captions
    "accent":        "#4f46e5",   # primary accent (indigo 600)
    "accent_hover":  "#4338ca",
    "accent_soft":   "#eef1fe",   # accent tint background
    "pass":          "#15803d",
    "pass_soft":     "#e9f7ef",
    "warn":          "#b45309",
    "warn_soft":     "#fdf5e6",
    "fail":          "#b91c1c",
    "fail_soft":     "#fdeeee",
    "neutral":       "#6b7280",
    "neutral_soft":  "#eef1f4",
}

# Backwards-compatible aliases so pages can use the shorter, intuitive names.
TOKENS["muted"] = TOKENS["text_muted"]
TOKENS["subtle"] = TOKENS["text_subtle"]

# Per-agent accent used for avatars / accents. Muted, professional hues.
AGENT_ACCENT = {
    "PIPELINE_TROUBLESHOOTING": "#4f46e5",  # indigo
    "INFRA_PROVISIONING":       "#0f766e",  # teal
    "FINOPS_OPTIMIZATION":      "#b45309",  # amber-brown
    "PROJECT_MANAGEMENT":       "#6d28d9",  # violet
}

AGENT_INITIALS = {
    "PIPELINE_TROUBLESHOOTING": "PT",
    "INFRA_PROVISIONING":       "IP",
    "FINOPS_OPTIMIZATION":      "FO",
    "PROJECT_MANAGEMENT":       "PM",
}


def agent_accent(code: str) -> str:
    return AGENT_ACCENT.get(code, TOKENS["accent"])


def agent_initials(code: str, label: str | None = None) -> str:
    if code in AGENT_INITIALS:
        return AGENT_INITIALS[code]
    words = (label or code.replace("_", " ")).split()
    return ("".join(w[0] for w in words[:2]) or "AG").upper()


# ── CSS ─────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    t = TOKENS
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ── Base ─────────────────────────────────────────────────────── */
        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        .stApp {{ background: {t['bg']}; }}
        .block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1320px; }}

        h1, h2, h3, h4 {{ color: {t['text']}; letter-spacing: -0.01em; }}
        h1 {{ font-weight: 800; font-size: 1.9rem; }}
        h2 {{ font-weight: 700; }}
        a {{ color: {t['accent']}; text-decoration: none; }}

        /* ── Sidebar (light, minimal) ─────────────────────────────────── */
        section[data-testid="stSidebar"] {{
            background: {t['surface']};
            border-right: 1px solid {t['border']};
        }}
        section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
        section[data-testid="stSidebar"] * {{ color: {t['text']}; }}

        /* Sidebar nav rendered as radio — clean list style */
        section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 2px; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label {{
            padding: 9px 12px; border-radius: 9px; margin: 0;
            transition: background .15s ease; cursor: pointer;
            font-size: 14px; font-weight: 500; color: {t['text_muted']};
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
            background: {t['surface_2']}; color: {t['text']};
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
            background: {t['accent_soft']}; color: {t['accent']}; font-weight: 600;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}

        section[data-testid="stSidebar"] .stButton button {{
            background: {t['surface']}; border: 1px solid {t['border_strong']};
            color: {t['text_muted']}; border-radius: 9px; width: 100%; font-weight: 500;
        }}
        section[data-testid="stSidebar"] .stButton button:hover {{
            background: {t['surface_2']}; color: {t['text']}; border-color: {t['neutral']};
        }}

        /* ── Cards ────────────────────────────────────────────────────── */
        /* Unified card radius + shadow token — change in ONE place */
        .kpi-card, .card, .agent-card, .result-card {{
            background: {t['surface']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(16,24,40,.05);
            transition: border-color .2s, box-shadow .2s;
        }}
        .kpi-card {{ padding: 18px 20px; }}
        .kpi-card:hover, .agent-card:hover {{
            border-color: {t['border_strong']}; box-shadow: 0 4px 14px rgba(16,24,40,.08);
        }}
        .card   {{ padding: 20px 22px; margin-bottom: 14px; }}
        .agent-card  {{ padding: 16px 18px; margin-bottom: 12px; }}
        .result-card {{ padding: 22px 24px; margin-bottom: 16px; }}

        .kpi-label {{ font-size: 12.5px; color: {t['text_muted']}; font-weight: 500; margin-bottom: 6px;
                      text-transform: uppercase; letter-spacing: .04em; }}
        .kpi-value {{ font-size: 30px; font-weight: 800; color: {t['text']}; line-height: 1.1; }}
        .kpi-help  {{ font-size: 12px; color: {t['text_subtle']}; margin-top: 4px; }}

        .avatar {{
            width: 38px; height: 38px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 13px; color: #fff; letter-spacing: .02em;
        }}
        .rec-card {{
            background: {t['surface_2']}; border: 1px solid {t['border']};
            border-left: 3px solid {t['accent']};
            border-radius: 12px; padding: 12px 15px; margin-bottom: 8px;
            font-size: 14px; color: {t['text']};
        }}

        /* ── Drift alerts ─────────────────────────────────────────────── */
        .drift-alert-high, .drift-alert-medium, .drift-alert-low {{
            border-radius: 12px; padding: 13px 16px; margin-bottom: 9px; border: 1px solid;
        }}
        .drift-alert-high   {{ background: {t['fail_soft']}; border-color: #f3c9c9; border-left: 4px solid {t['fail']}; }}
        .drift-alert-medium {{ background: {t['warn_soft']}; border-color: #eddcc0; border-left: 4px solid {t['warn']}; }}
        .drift-alert-low    {{ background: {t['pass_soft']}; border-color: #c6e6d3; border-left: 4px solid {t['pass']}; }}

        /* ── Badges & pills ───────────────────────────────────────────── */
        .badge {{
            display: inline-flex; align-items: center; gap: 6px;
            border-radius: 7px; padding: 4px 11px; font-weight: 600;
            font-size: 12.5px; letter-spacing: .02em; border: 1px solid transparent;
        }}
        .badge-pass    {{ background: {t['pass_soft']}; color: {t['pass']}; border-color: #c6e6d3; }}
        .badge-warning {{ background: {t['warn_soft']}; color: {t['warn']}; border-color: #eddcc0; }}
        .badge-fail    {{ background: {t['fail_soft']}; color: {t['fail']}; border-color: #f3c9c9; }}
        .badge-neutral {{ background: {t['neutral_soft']}; color: {t['neutral']}; border-color: {t['border']}; }}
        .badge-running {{ background: {t['accent_soft']}; color: {t['accent']}; border-color: #d6dcfb; }}
        .badge-dot {{ width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}

        .status-healthy  {{ color: {t['pass']}; font-weight: 600; }}
        .status-at-risk  {{ color: {t['warn']}; font-weight: 600; }}
        .status-critical {{ color: {t['fail']}; font-weight: 600; }}
        .status-no-data  {{ color: {t['text_subtle']}; font-weight: 500; }}

        .pill {{
            display: inline-block; background: {t['surface_2']};
            border: 1px solid {t['border']}; border-radius: 999px;
            padding: 3px 10px; font-size: 11.5px; color: {t['text_muted']}; font-weight: 500;
        }}
        .muted {{ color: {t['text_muted']}; font-size: 13px; }}
        .subtle {{ color: {t['text_subtle']}; font-size: 12px; }}

        /* ── Readiness bar ────────────────────────────────────────────── */
        .readiness-bar-bg {{ background: {t['neutral_soft']}; border-radius: 999px; height: 8px; width: 100%; overflow: hidden; }}
        .readiness-bar-fill {{ height: 8px; border-radius: 999px; transition: width .5s ease; }}

        /* ── Plotly charts — rounded, bordered, consistent ────────────── */
        [data-testid="stPlotlyChart"] > div,
        [data-testid="stPlotlyChart"] iframe {{
            border-radius: 12px !important;
            overflow: hidden;
        }}
        [data-testid="stPlotlyChart"] {{
            border: 1px solid {t['border']};
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(16,24,40,.05);
        }}

        /* ── Info/meta cards (inline HTML) ────────────────────────────── */
        /* Standardise any raw div cards emitted by pages */
        .sup-info-card {{
            background: {t['surface']}; border: 1px solid {t['border']};
            border-radius: 12px; padding: 14px 16px; margin-bottom: 4px;
            box-shadow: 0 1px 2px rgba(16,24,40,.04);
        }}

        /* ── Flow ─────────────────────────────────────────────────────── */
        .flow-wrap {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }}
        .flow-step {{
            display: inline-flex; align-items: center; gap: 7px;
            background: {t['surface']}; border: 1px solid {t['border']};
            border-radius: 9px; padding: 7px 12px; font-size: 13px;
            font-weight: 500; color: {t['text']};
        }}
        .flow-step.active {{ background: {t['accent_soft']}; border-color: #d6dcfb; color: {t['accent']}; font-weight: 600; }}
        .flow-num {{
            width: 18px; height: 18px; border-radius: 5px; background: {t['neutral_soft']};
            color: {t['text_muted']}; font-size: 11px; font-weight: 700;
            display: inline-flex; align-items: center; justify-content: center;
        }}
        .flow-step.active .flow-num {{ background: {t['accent']}; color: #fff; }}
        .flow-arrow {{ color: {t['text_subtle']}; font-size: 14px; }}

        /* ── Section header ───────────────────────────────────────────── */
        .section-header {{
            font-size: 15px; font-weight: 700; color: {t['text']};
            padding-bottom: 9px; margin: 4px 0 14px;
            border-bottom: 1px solid {t['border']}; letter-spacing: -0.005em;
        }}
        .page-caption {{ color: {t['text_muted']}; font-size: 14.5px; margin-top: -6px; margin-bottom: 8px; }}

        /* ── Rule rows ────────────────────────────────────────────────── */
        .rule-pass {{ color: {t['pass']}; font-weight: 600; }}
        .rule-fail {{ color: {t['fail']}; font-weight: 600; }}

        /* ── Tabs ─────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {t['border']}; }}
        .stTabs [data-baseweb="tab"] {{
            font-weight: 500; color: {t['text_muted']}; padding: 8px 14px;
        }}
        .stTabs [aria-selected="true"] {{ color: {t['accent']}; font-weight: 600; }}

        /* Divider spacing */
        hr {{ margin: 1.1rem 0; border-color: {t['border']}; }}
        [data-testid="stMetricValue"] {{ font-weight: 800; color: {t['text']}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Brand wordmark ───────────────────────────────────────────────────────────

def brand_wordmark() -> None:
    t = TOKENS
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:11px; padding:4px 2px 2px;">
          <div style="width:34px; height:34px; border-radius:9px;
                      background:linear-gradient(135deg,{t['accent']},{t['accent_hover']});
                      display:flex; align-items:center; justify-content:center;">
            <div style="width:14px; height:14px; border:2.4px solid #fff; border-radius:4px;"></div>
          </div>
          <div style="line-height:1.15;">
            <div style="font-weight:800; font-size:15px; color:{t['text']};">Supervisor Agent</div>
            <div style="font-size:11px; color:{t['text_subtle']}; font-weight:500;">Supervisor Agent Platform</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Verdict badge ────────────────────────────────────────────────────────────

def verdict_badge(verdict: str, large: bool = False) -> None:
    klass = "badge-pass" if verdict == "PASS" else "badge-warning" if verdict == "WARNING" else "badge-fail"
    size = "font-size:15px; padding:7px 16px;" if large else ""
    st.markdown(
        f'<span class="badge {klass}" style="{size}"><span class="badge-dot"></span>{verdict}</span>',
        unsafe_allow_html=True,
    )


# ── KPI metric card ──────────────────────────────────────────────────────────

def kpi(label: str, value: Any, delta: Any = None, helper: str | None = None) -> None:
    delta_html = ""
    if delta is not None:
        dcolor = TOKENS["pass"] if str(delta).lstrip().startswith(("+",)) else TOKENS["text_muted"]
        delta_html = f'<div style="font-size:12.5px; color:{dcolor}; font-weight:600; margin-top:2px;">{delta}</div>'
    help_html = f'<div class="kpi-help">{helper}</div>' if helper else ""
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          {delta_html}{help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Agent health card ────────────────────────────────────────────────────────

def agent_health_card(agent_code: str, health: dict[str, Any]) -> None:
    accent = agent_accent(agent_code)
    initials = agent_initials(agent_code, health.get("label"))
    label = health.get("label", agent_code)
    status = health.get("status", "NO_DATA")
    pass_rate = health.get("pass_rate", 0.0)
    total = health.get("total", 0)
    lifecycle = health.get("lifecycle", "")
    last_run = str(health.get("last_run") or "—")[:16]

    status_css = {
        "HEALTHY": "status-healthy",
        "AT_RISK": "status-at-risk",
        "CRITICAL": "status-critical",
    }.get(status, "status-no-data")
    status_label = {
        "HEALTHY": "Healthy",
        "AT_RISK": "At Risk",
        "CRITICAL": "Critical",
        "NO_DATA": "No Data",
    }.get(status, status)

    st.markdown(
        f"""
        <div class="agent-card">
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="avatar" style="background:{accent};">{initials}</div>
            <div style="flex:1; min-width:0;">
              <div style="font-weight:700; font-size:13.5px; color:#111827;
                          white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{label}</div>
              <div class="{status_css}" style="font-size:12.5px; display:flex; align-items:center; gap:5px;">
                <span style="width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;"></span>
                {status_label}
              </div>
            </div>
          </div>
          <div style="display:flex; gap:22px; margin-top:14px;">
            <div>
              <div style="font-size:19px; font-weight:800; color:{accent};">{pass_rate:.0f}%</div>
              <div class="subtle">Pass rate</div>
            </div>
            <div>
              <div style="font-size:19px; font-weight:800; color:#374151;">{total}</div>
              <div class="subtle">Validations</div>
            </div>
          </div>
          <div style="margin-top:13px; display:flex; align-items:center; justify-content:space-between;">
            <span class="pill">{lifecycle}</span>
            <span class="subtle">Last run · {last_run}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Production readiness bar ─────────────────────────────────────────────────

def readiness_bar(score: float, color: str, label: str) -> None:
    pct = min(100, max(0, score))
    st.markdown(
        f"""
        <div style="margin-bottom:11px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
            <span style="font-size:13px; color:#374151; font-weight:500;">{label}</span>
            <span style="font-size:13px; font-weight:700; color:{color};">{pct:.0f}<span style="color:#98a1ad; font-weight:500;">/100</span></span>
          </div>
          <div class="readiness-bar-bg">
            <div class="readiness-bar-fill" style="width:{pct}%; background:{color};"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Flow visualization ────────────────────────────────────────────────────────

def render_flow(detected_tool: str | None = None) -> None:
    steps = [
        "Record",
        "Orchestrator",
        detected_tool or "Selected Tool",
        "Rule Checks",
        "LLM Judge",
        "Synthesis",
        "Store",
    ]
    active_idx = 2 if detected_tool else -1
    parts = ['<div class="flow-wrap">']
    for i, label in enumerate(steps):
        active = " active" if i == active_idx else ""
        parts.append(
            f'<span class="flow-step{active}"><span class="flow-num">{i+1}</span>{label}</span>'
        )
        if i < len(steps) - 1:
            parts.append('<span class="flow-arrow">→</span>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ── Drift alert banner ────────────────────────────────────────────────────────

def drift_alert(alert: dict[str, Any]) -> None:
    sev = alert.get("severity", "LOW")
    css = f"drift-alert-{sev.lower()}"
    color = {"HIGH": TOKENS["fail"], "MEDIUM": TOKENS["warn"], "LOW": TOKENS["pass"]}.get(sev, TOKENS["neutral"])
    msg = alert.get("message", "")
    action = alert.get("action", "")
    st.markdown(
        f"""
        <div class="{css}">
          <div style="font-weight:600; font-size:13.5px; color:#111827; display:flex; align-items:center; gap:7px;">
            <span style="font-size:11px; font-weight:700; color:{color}; text-transform:uppercase; letter-spacing:.05em;">{sev}</span>
            <span>{msg}</span>
          </div>
          <div class="muted" style="margin-top:3px;">{action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Recommendation card ────────────────────────────────────────────────────────

def recommendation_card(text: str, severity: str = "") -> None:
    """Render a clean recommendation card with a severity pill and plain-English text.

    No raw codes, no underscores, no bold-header patterns — just a readable card.
    """
    import re
    t = TOKENS
    sev_upper = severity.upper()

    # Severity pill config
    _pill = {
        "CRITICAL": ("#b91c1c", "#fdeeee", "Critical"),
        "HIGH":     ("#c2410c", "#fff4ed", "High"),
        "MEDIUM":   ("#b45309", "#fdf5e6", "Medium"),
        "LOW":      ("#4b5563", "#f3f4f6", "Low"),
        "INFO":     ("#4f46e5", "#eef1fe", "Info"),
        "PASS":     ("#15803d", "#e9f7ef", "Passed"),
    }
    pill_color, pill_bg, pill_label = _pill.get(sev_upper, ("#4f46e5", "#eef1fe", sev_upper.title() or "Note"))

    # Left border colour
    border_color = {
        "CRITICAL": t["fail"], "HIGH": "#c2410c", "MEDIUM": t["warn"],
        "LOW": t["neutral"], "INFO": t["accent"], "PASS": t["pass"],
    }.get(sev_upper, t["accent"])

    # Strip any remaining **bold** markdown — not needed in clean cards
    clean_text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    st.markdown(
        f"""<div style="background:{t['surface']};border:1px solid {t['border']};
            border-left:4px solid {border_color};border-radius:12px;
            padding:16px 20px;margin-bottom:10px;
            box-shadow:0 1px 3px rgba(16,24,40,.04);">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:9px;">
            <span style="font-size:11px;font-weight:700;letter-spacing:.05em;
                         color:{pill_color};background:{pill_bg};
                         border-radius:6px;padding:2px 9px;text-transform:uppercase;">{pill_label}</span>
          </div>
          <div style="font-size:14px;color:{t['text']};line-height:1.7;">{clean_text}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ── Severity label (plain, no emoji) ─────────────────────────────────────────

def severity_icon(severity: str) -> str:
    return {
        "CRITICAL": "Critical",
        "HIGH": "High",
        "MEDIUM": "Medium",
        "LOW": "Low",
        "INFO": "Info",
    }.get(severity, severity.title() if severity else "")


# ── Section header ────────────────────────────────────────────────────────────

def section_header(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def page_caption(text: str) -> None:
    st.markdown(f'<div class="page-caption">{text}</div>', unsafe_allow_html=True)
