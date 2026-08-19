from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from supervisor_control_tower.config import get_settings
from supervisor_control_tower.db import Database
from supervisor_control_tower.models import AppUser
from supervisor_control_tower.repositories import SupervisorRepository
from supervisor_control_tower.ui.components import page_header, render_decision_card
from supervisor_control_tower.validation_service import ValidationService


def render(database: Database, user: AppUser) -> None:
    page_header(
        "Evaluate agent output",
        "Select an enterprise record. Routing, controls, LLM review and governance are applied automatically.",
    )
    with database.transaction() as connection:
        records = SupervisorRepository(connection).list_active_records()
    if not records:
        st.warning("No active records are available. Run the seed command or load records into the Excel store.")
        return

    record_map = {record.id: record for record in records}
    selected_id = st.selectbox(
        "Enterprise record",
        options=list(record_map),
        format_func=lambda record_id: record_map[record_id].dropdown_label,
    )
    focus = st.text_area(
        "Reviewer focus — optional",
        placeholder="Example: verify evidence traceability, financial calculations and approval readiness",
        max_chars=2000,
    )

    if st.button("Run evaluation", type="primary", use_container_width=True):
        try:
            with st.spinner("Evaluating deterministic controls, context, memory and LLM judgement..."):
                result = ValidationService(get_settings(), database).run_validation(selected_id, focus or None, user)
            st.session_state["latest_evaluation"] = result.model_dump(mode="json")
        except Exception as exc:
            st.error(f"Evaluation failed: {exc}")

    raw = st.session_state.get("latest_evaluation")
    if not raw:
        return
    from supervisor_control_tower.models import ValidationRunResult

    result = ValidationRunResult.model_validate(raw)
    st.markdown("---")
    render_decision_card(result.final)

    with st.expander("View technical details"):
        left, right = st.columns(2)
        with left:
            st.markdown("**Routing**")
            st.write({
                "agent": result.routing.detected_agent_code,
                "tool": result.routing.selected_tool,
                "method": result.routing.routing_method,
                "confidence": result.routing.confidence,
                "reason": result.routing.reason,
            })
            st.markdown("**Assurance score calculation**")
            st.dataframe(
                pd.DataFrame(
                    [{"Component": key.replace("_", " ").title(), "Score": value} for key, value in result.final.score_breakdown.items()]
                ),
                use_container_width=True,
                hide_index=True,
            )
        with right:
            st.markdown("**LLM Judge**")
            st.write(result.llm_judgement.analysis)
            st.write(result.llm_judgement.quality_dimensions)
            st.markdown("**Context and memory**")
            st.write(result.context.model_dump())
            st.write(result.memory.summary)

        st.markdown("**Deterministic controls**")
        control_frame = pd.DataFrame([
            {
                "Control": item.rule_name,
                "Severity": item.severity.value,
                "Passed": item.passed,
                "Mandatory": item.mandatory,
                "Message": item.message,
            }
            for item in result.tool_result.rule_results
        ])
        st.dataframe(control_frame, use_container_width=True, hide_index=True)
        st.download_button(
            "Download evaluation JSON",
            data=json.dumps(result.model_dump(mode="json"), indent=2),
            file_name=f"{result.record.external_reference}_{result.run_id}.json",
            mime="application/json",
        )
