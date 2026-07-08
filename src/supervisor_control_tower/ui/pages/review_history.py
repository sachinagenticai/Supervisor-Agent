from __future__ import annotations

import json

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AgentCode, Verdict
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import (
    section_header, severity_icon, verdict_badge, page_caption, TOKENS
)


def render(db: Database) -> None:
    st.title("Review History")
    page_caption("Complete audit trail of all validation runs. Filter, drill down, and review rule-level detail.")

    # ── Filters ───────────────────────────────────────────────────────────
    with st.expander("Filter runs", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
        with fc1:
            verdict_filter = st.selectbox("Verdict", ["All"] + [v.value for v in Verdict])
        with fc2:
            agent_filter = st.selectbox("Agent", ["All"] + [a.value for a in AgentCode])
        with fc3:
            status_filter = st.selectbox("Status", ["All", "COMPLETED", "ERROR", "RUNNING"])
        with fc4:
            search = st.text_input("Search run ID / record title", placeholder="type to filter…")

    with db.transaction() as conn:
        repo = SupervisorRepository(conn)
        rows = repo.history(
            verdict=verdict_filter if verdict_filter != "All" else None,
            agent=agent_filter if agent_filter != "All" else None,
            search=search or None,
        )

    if not rows:
        st.info("No validation history found for the selected filters.")
        return

    df = pd.DataFrame(rows)

    # ── Summary charts ────────────────────────────────────────────────────
    if _PLOTLY and len(df) > 1:
        ch1, ch2 = st.columns(2)
        with ch1:
            section_header("Verdict distribution")
            vcounts = df["verdict"].value_counts().reset_index()
            vcounts.columns = ["verdict", "count"]
            colors_map = {"PASS": "#15803d", "WARNING": "#b45309", "FAIL": "#b91c1c"}
            fig = px.bar(vcounts, x="verdict", y="count",
                         color="verdict",
                         color_discrete_map=colors_map,
                         height=220, text="count")
            fig.update_layout(margin=dict(l=0, r=0, t=4, b=0),
                               paper_bgcolor="white", plot_bgcolor="white",
                               font=dict(family="Inter, sans-serif", color="#606a78"),
                               showlegend=False, xaxis_title="", yaxis_title="Runs",
                               uirevision="history_verdict_bar")
            st.plotly_chart(fig, width="stretch", key="history_verdict_bar")

        with ch2:
            section_header("Agent coverage")
            acounts = df["detected_agent_code"].value_counts().reset_index()
            acounts.columns = ["agent", "count"]
            acounts["agent"] = acounts["agent"].str.replace("_", " ").str.title()
            fig2 = px.pie(acounts, names="agent", values="count",
                          hole=0.5, height=220,
                          color_discrete_sequence=["#4f46e5", "#0f766e", "#b45309", "#6d28d9", "#9aa4b2"])
            fig2.update_layout(margin=dict(l=0, r=0, t=4, b=0),
                                paper_bgcolor="white", showlegend=True,
                                font=dict(family="Inter, sans-serif", color="#606a78"),
                                legend=dict(font=dict(size=10)),
                                uirevision="history_agent_pie")
            st.plotly_chart(fig2, width="stretch", key="history_agent_pie")

    # ── Main history table ─────────────────────────────────────────────────
    section_header(f"{len(df)} Validation Runs")
    display_df = df[["run_id", "timestamp", "detected_agent_code", "record", "verdict", "tag", "confidence", "initiated_by"]].copy()
    display_df.columns = ["Run ID", "Timestamp", "Agent", "Record", "Verdict", "Tag", "Confidence", "By"]
    display_df["Agent"] = display_df["Agent"].str.replace("_", " ").str.title()
    display_df["Run ID"] = display_df["Run ID"].astype(str).str[:8] + "…"
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=300)

    # ── Export ─────────────────────────────────────────────────────────────
    export_df = df[["run_id", "timestamp", "detected_agent_code",
                    "record", "verdict", "tag", "confidence", "initiated_by"]].copy()
    export_df.columns = ["run_id", "timestamp", "agent", "record", "verdict", "tag", "confidence", "initiated_by"]
    ec1, ec2, _ = st.columns([1, 1, 3])
    with ec1:
        st.download_button(
            "Download CSV", export_df.to_csv(index=False).encode("utf-8"),
            file_name="validation_history.csv", mime="text/csv", use_container_width=True,
        )
    with ec2:
        st.download_button(
            "Download JSON", export_df.to_json(orient="records", indent=2).encode("utf-8"),
            file_name="validation_history.json", mime="application/json", use_container_width=True,
        )

    # ── Drill-down ─────────────────────────────────────────────────────────
    st.markdown("---")
    section_header("Drill Into a Run")
    full_run_ids = df["run_id"].tolist()
    selected_idx = st.selectbox(
        "Select run ID",
        range(len(full_run_ids)),
        format_func=lambda i: f"{full_run_ids[i][:12]}… — {df.iloc[i].get('record','')[:50]} — {df.iloc[i].get('verdict','')}",
    )
    selected_run_id = full_run_ids[selected_idx]

    with db.transaction() as conn:
        detail = SupervisorRepository(conn).run_detail(selected_run_id)

    run = detail["run"]
    verdict_val = str(run.get("final_verdict") or "")
    verdict_color = {"PASS": TOKENS["pass"], "WARNING": TOKENS["warn"], "FAIL": TOKENS["fail"]}.get(verdict_val, TOKENS["muted"])

    # ── Run header ────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                    border-left:4px solid {verdict_color}; border-radius:12px; padding:18px; margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
            <div>
              <div style="font-weight:700; font-size:16px; color:{TOKENS['text']};">{run.get("record_title","")}</div>
              <div style="color:{TOKENS['muted']}; font-size:13px; margin-top:4px;">
                {run.get("external_reference","")} · {run.get("source_system","")} · {run.get("record_type","")}
              </div>
            </div>
            <div style="text-align:right;">
              <span style="font-size:19px; font-weight:800; color:{verdict_color};">{verdict_val}</span>
              <div style="font-size:12px; color:{TOKENS['muted']};">{str(run.get("completed_at",""))[:16]}</div>
            </div>
          </div>
          <div style="margin-top:12px; color:{TOKENS['text']}; font-size:13.5px; line-height:1.5;">{run.get("final_reason","")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Metrics ───────────────────────────────────────────────────────────
    dm1, dm2, dm3, dm4 = st.columns(4)
    dm1.metric("Agent", str(run.get("detected_agent_code","")).replace("_"," ").title())
    dm2.metric("Tool", str(run.get("selected_tool_code","")).replace("_tool","").replace("_"," ").title())
    dm3.metric("Confidence", f"{float(run.get('final_confidence') or 0):.0%}")
    dm4.metric("Tag", str(run.get("final_tag","")))

    st.download_button(
        "Download run detail (JSON)",
        json.dumps(detail, default=str, indent=2).encode("utf-8"),
        file_name=f"run_{str(selected_run_id)[:8]}.json",
        mime="application/json",
    )

    dtab1, dtab2, dtab3, dtab4 = st.tabs(["Rules", "LLM Judge", "Routing", "Audit"])

    with dtab1:
        if detail["rules"]:
            rdf = pd.DataFrame(detail["rules"])
            rdf["Result"] = rdf["passed"].apply(lambda p: "PASS" if p else "FAIL")
            st.dataframe(
                rdf[["rule_code", "rule_name", "severity", "Result", "tag", "message"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No rule results stored for this run.")

    with dtab2:
        if detail["llm"]:
            llm = detail["llm"]
            judge_verdict = str(llm.get("judge_verdict", ""))
            jcolor = {"PASS": TOKENS["pass"], "WARNING": TOKENS["warn"], "FAIL": TOKENS["fail"]}.get(judge_verdict, TOKENS["muted"])
            st.markdown(
                f"""
                <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                            border-left:4px solid {jcolor}; border-radius:12px; padding:16px 18px;">
                  <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em;
                              color:{TOKENS['muted']}; margin-bottom:4px;">LLM Judge</div>
                  <div style="font-weight:700; color:{jcolor}; font-size:15px;">
                    {judge_verdict} · {float(llm.get('confidence') or 0):.0%}
                  </div>
                  <div style="color:{TOKENS['text']}; margin-top:8px; font-size:13.5px; line-height:1.5;">{llm.get("reason","")}</div>
                  <div style="font-size:11px; color:{TOKENS['muted']}; margin-top:10px;">
                    Model: {llm.get("model_name","")} · Prompt: {llm.get("prompt_version","")}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            findings = llm.get("findings", [])
            if findings:
                st.markdown("**Judge findings**")
                _sev_color = {"CRITICAL": TOKENS["fail"], "HIGH": "#c2410c", "MEDIUM": TOKENS["warn"],
                              "LOW": TOKENS["muted"], "INFO": TOKENS["muted"]}
                for f in findings if isinstance(findings, list) else []:
                    sev = f.get("severity", "") if isinstance(f, dict) else ""
                    col = _sev_color.get(sev, TOKENS["muted"])
                    msg = f.get("message", "") if isinstance(f, dict) else str(f)
                    tag = f.get('tag', '') if isinstance(f, dict) else ''
                    st.markdown(
                        f"""
                        <div style="display:flex; gap:10px; align-items:baseline; padding:7px 0;
                                    border-bottom:1px solid {TOKENS['border']};">
                          <span style="font-size:10px; font-weight:700; letter-spacing:0.06em; color:{col};
                                       background:{TOKENS['bg']}; border:1px solid {TOKENS['border']};
                                       border-radius:5px; padding:2px 7px; white-space:nowrap;">{sev}</span>
                          <span style="font-size:12px; color:{TOKENS['muted']}; font-family:monospace;">{tag}</span>
                          <span style="font-size:13px; color:{TOKENS['text']};">{msg}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No LLM judgement stored.")

    with dtab3:
        st.markdown(f"**Detected agent:** `{run.get('detected_agent_code','')}`")
        st.markdown(f"**Selected tool:** `{run.get('selected_tool_code','')}`")
        st.markdown(f"**Routing reason:** {run.get('routing_reason','')}")
        st.markdown(f"**Routing confidence:** {float(run.get('routing_confidence') or 0):.0%}")
        if run.get("comments"):
            st.markdown(f"**User comments:** {run.get('comments')}")

    with dtab4:
        if detail["audit"]:
            adf = pd.DataFrame(detail["audit"])[["event_type", "created_at"]]
            adf.columns = ["Event", "Timestamp"]
            st.dataframe(adf, use_container_width=True, hide_index=True)
        else:
            st.info("No audit trail stored.")
