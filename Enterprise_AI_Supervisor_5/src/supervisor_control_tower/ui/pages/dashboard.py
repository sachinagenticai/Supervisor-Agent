from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from supervisor_control_tower.db import Database
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import page_header


def render(database: Database) -> None:
    page_header(
        "AI assurance dashboard",
        "A business view of agent readiness, material risk and recent evaluation performance.",
    )
    with database.transaction() as connection:
        repository = SupervisorRepository(connection)
        metrics = repository.dashboard_metrics()
        health = repository.agent_health_metrics()
        trend = repository.trend_data(days=30)
        recent = repository.recent_activity(limit=6)
        failures = repository.rule_failure_stats(limit=5)
        agents = repository.list_registered_agents()

    columns = st.columns(5)
    columns[0].metric("Evaluations", metrics["total_validations"])
    columns[1].metric("Ready", metrics["ready_count"])
    columns[2].metric("Needs review", metrics["needs_review_count"])
    columns[3].metric("Blocked", metrics["blocked_count"])
    columns[4].metric("Average assurance", f"{metrics['average_assurance']:.0%}")

    st.subheader("Agent health")
    if health:
        health_frame = pd.DataFrame(health)
        health_frame["Ready rate"] = health_frame["ready_rate"].map(lambda value: f"{value:.0%}")
        health_frame["Average assurance"] = health_frame["average_assurance"].map(lambda value: f"{value:.0%}")
        st.dataframe(
            health_frame[["agent_name", "lifecycle_status", "total_runs", "Ready rate", "blocked_count", "Average assurance"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "agent_name": "Agent",
                "lifecycle_status": "Stage",
                "total_runs": "Evaluations",
                "blocked_count": "Blocked",
            },
        )
    else:
        st.info("No agent evaluations are available yet.")

    left, right = st.columns([1.65, 1])
    with left:
        st.subheader("30-day decision trend")
        if trend:
            frame = pd.DataFrame(trend)
            long = frame.melt(
                id_vars=["date"],
                value_vars=["ready", "needs_review", "blocked"],
                var_name="Decision",
                value_name="Evaluations",
            )
            long["Decision"] = long["Decision"].str.replace("_", " ").str.title()
            chart = px.line(long, x="date", y="Evaluations", color="Decision", markers=True)
            chart.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("Trend data will appear after evaluations are completed.")
    with right:
        st.subheader("Most frequent control gaps")
        if failures:
            st.dataframe(
                pd.DataFrame(failures)[["rule_name", "severity", "failure_count"]],
                use_container_width=True,
                hide_index=True,
                column_config={"rule_name": "Control", "severity": "Severity", "failure_count": "Failures"},
            )
        else:
            st.success("No control failures are recorded.")

    st.subheader("Recent evaluations")
    if recent:
        frame = pd.DataFrame(recent)
        frame["Assurance"] = frame["assurance_score"].map(lambda value: f"{value:.0%}")
        frame["Decision"] = frame["business_decision"].str.replace("_", " ").str.title()
        st.dataframe(
            frame[["external_reference", "record_title", "agent_code", "Decision", "Assurance", "completed_at"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "external_reference": "Reference",
                "record_title": "Record",
                "agent_code": "Agent",
                "completed_at": "Completed",
            },
        )

    with st.expander("Agent library"):
        library_rows = [
            {
                "Agent": item.get("agent_name"),
                "Code": item.get("agent_code"),
                "Version": item.get("version"),
                "Owner": item.get("owner"),
                "Stage": item.get("lifecycle_status"),
                "Capabilities": ", ".join(item.get("capabilities") or []),
                "Rule pack": item.get("rule_pack_id"),
            }
            for item in agents
            if item.get("enabled")
        ]
        st.dataframe(pd.DataFrame(library_rows), use_container_width=True, hide_index=True)
        st.caption(
            "New configuration-only agents are added in config/agents.json and config/rule_packs.json. "
            "Custom Python plugins are optional for complex domains."
        )
