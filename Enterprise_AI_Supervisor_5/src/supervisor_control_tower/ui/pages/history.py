from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AppUser
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import page_header


def render(database: Database, user: AppUser) -> None:
    page_header(
        "Evaluation history",
        "Search, review and export the complete audit trail for previous agent evaluations.",
    )
    with database.transaction() as connection:
        repository = SupervisorRepository(connection)
        agents = [item["agent_code"] for item in repository.list_registered_agents() if item["enabled"]]

    filter_columns = st.columns([2, 1, 1])
    search = filter_columns[0].text_input("Search", placeholder="Reference, title, tag or reviewer")
    agent = filter_columns[1].selectbox("Agent", ["All"] + sorted(agents))
    decision = filter_columns[2].selectbox("Decision", ["All", "READY", "NEEDS_REVIEW", "BLOCKED"])

    with database.transaction() as connection:
        repository = SupervisorRepository(connection)
        rows = repository.history(
            search=search or None,
            agent_code=None if agent == "All" else agent,
            decision=None if decision == "All" else decision,
            limit=500,
        )
    if not rows:
        st.info("No evaluations match the selected filters.")
        return

    frame = pd.DataFrame(rows)
    frame["Assurance"] = frame["assurance_score"].map(lambda value: f"{value:.0%}")
    frame["Decision"] = frame["business_decision"].str.replace("_", " ").str.title()
    st.dataframe(
        frame[["external_reference", "record_title", "agent_code", "Decision", "Assurance", "primary_tag", "completed_at"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "external_reference": "Reference",
            "record_title": "Record",
            "agent_code": "Agent",
            "primary_tag": "Primary tag",
            "completed_at": "Completed",
        },
    )

    selected_run = st.selectbox(
        "Open evaluation",
        options=[row["run_id"] for row in rows],
        format_func=lambda run_id: next(
            f"{row['external_reference']} · {row['business_decision'].replace('_', ' ').title()} · {row['completed_at']}"
            for row in rows if row["run_id"] == run_id
        ),
    )
    with database.transaction() as connection:
        detail = SupervisorRepository(connection).run_detail(selected_run)
    if not detail:
        return

    run = detail["run"]
    st.markdown(f"### {detail['record'].get('external_reference')} — {detail['record'].get('record_title')}")
    st.write(run.get("final_reason"))
    st.caption(f"Recommended action: {run.get('recommended_action')}")
    with st.expander("Controls and judge evidence"):
        st.json({
            "routing": {
                "agent": run.get("detected_agent_code"),
                "tool": run.get("selected_tool_code"),
                "confidence": run.get("routing_confidence"),
                "reason": run.get("routing_reason"),
            },
            "rules": detail["rule_results"],
            "llm_judgement": detail["llm_judgement"],
            "audit_events": detail["audit_events"],
        })
    st.download_button(
        "Download audit JSON",
        data=json.dumps(detail, indent=2, default=str),
        file_name=f"evaluation_{selected_run}.json",
        mime="application/json",
    )
