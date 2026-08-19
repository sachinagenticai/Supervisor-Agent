from __future__ import annotations

import html

import streamlit as st

from supervisor_control_tower.models import BusinessDecision, FinalSynthesis

TOKENS = {
    "ink": "#172033",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "surface": "#FFFFFF",
    "background": "#F6F8FB",
    "brand": "#2457D6",
    "ready": "#137A4B",
    "review": "#A15C00",
    "blocked": "#B42318",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {TOKENS['background']}; color: {TOKENS['ink']}; }}
        .block-container {{ max-width: 1220px; padding-top: 2rem; padding-bottom: 3rem; }}
        [data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {TOKENS['border']}; }}
        [data-testid="stMetric"] {{ background:#fff; border:1px solid {TOKENS['border']}; border-radius:14px; padding:15px 16px; }}
        .sup-title {{ font-size:30px; font-weight:760; letter-spacing:-.025em; margin:0; color:{TOKENS['ink']}; }}
        .sup-caption {{ color:{TOKENS['muted']}; font-size:14px; margin-top:5px; margin-bottom:24px; }}
        .sup-card {{ background:#fff; border:1px solid {TOKENS['border']}; border-radius:16px; padding:20px; box-shadow:0 2px 8px rgba(15,23,42,.035); }}
        .sup-label {{ color:{TOKENS['muted']}; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.055em; }}
        .sup-decision {{ font-size:28px; font-weight:800; margin:4px 0 6px; }}
        .sup-score {{ font-size:18px; font-weight:700; }}
        .sup-body {{ font-size:14px; line-height:1.65; color:{TOKENS['ink']}; }}
        .sup-small {{ color:{TOKENS['muted']}; font-size:12.5px; }}
        .sup-brand {{ font-size:18px; font-weight:800; color:{TOKENS['ink']}; padding:8px 2px 10px; }}
        .sup-agent-hero {{ background:linear-gradient(135deg,#FFFFFF 0%,#F8FAFF 100%); margin:8px 0 22px; }}
        .sup-badge {{ display:inline-block; padding:5px 9px; border-radius:999px; background:#E8F0FF; color:{TOKENS['brand']}; font-size:11px; font-weight:750; letter-spacing:.04em; text-transform:uppercase; margin-right:6px; }}
        .sup-badge-neutral {{ background:#EEF2F6; color:#475569; }}
        .sup-agent-meta {{ display:flex; flex-wrap:wrap; gap:10px 22px; color:{TOKENS['muted']}; font-size:12.5px; margin-top:16px; }}
        .sup-flow-step {{ background:#fff; border:1px solid {TOKENS['border']}; border-radius:14px; padding:16px; min-height:170px; margin-bottom:12px; }}
        .sup-flow-number {{ width:30px; height:30px; border-radius:9px; display:flex; align-items:center; justify-content:center; background:#E8F0FF; color:{TOKENS['brand']}; font-weight:800; margin-bottom:12px; }}
        .stButton > button {{ border-radius:10px; min-height:42px; font-weight:650; }}
        .stDownloadButton > button {{ border-radius:10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, caption: str) -> None:
    st.markdown(f'<h1 class="sup-title">{html.escape(title)}</h1>', unsafe_allow_html=True)
    st.markdown(f'<div class="sup-caption">{html.escape(caption)}</div>', unsafe_allow_html=True)


def brand_wordmark() -> None:
    st.markdown('<div class="sup-brand">Enterprise AI Supervisor</div>', unsafe_allow_html=True)


def decision_colour(decision: BusinessDecision | str) -> str:
    value = decision.value if isinstance(decision, BusinessDecision) else str(decision)
    return {
        BusinessDecision.READY.value: TOKENS["ready"],
        BusinessDecision.NEEDS_REVIEW.value: TOKENS["review"],
        BusinessDecision.BLOCKED.value: TOKENS["blocked"],
    }.get(value, TOKENS["muted"])


def render_decision_card(final: FinalSynthesis) -> None:
    colour = decision_colour(final.business_decision)
    display = final.business_decision.value.replace("_", " ").title()
    findings = "".join(
        f"<li>{html.escape(item)}</li>" for item in final.findings_summary[:4]
    ) or "<li>No material finding was identified.</li>"
    st.markdown(
        f"""
        <div class="sup-card" style="border-left:5px solid {colour};">
          <div class="sup-label">Business decision</div>
          <div class="sup-decision" style="color:{colour};">{display}</div>
          <div class="sup-score">AI Assurance {final.assurance_score:.0%} · {final.assurance_band.value.title()}</div>
          <p class="sup-body">{html.escape(final.reason)}</p>
          <div class="sup-label">Top findings</div>
          <ul class="sup-body">{findings}</ul>
          <div class="sup-label">Recommended action</div>
          <p class="sup-body" style="margin-bottom:0;">{html.escape(final.recommended_action)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
