from __future__ import annotations

import html
from collections.abc import Iterable

import pandas as pd
import streamlit as st

from supervisor_control_tower.agent_glossary import (
    agent_summary_row,
    filter_agents,
    humanize_identifier,
)
from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.config import Settings, get_settings
from supervisor_control_tower.models import AgentDefinition
from supervisor_control_tower.rules.engine import Rule
from supervisor_control_tower.rules.registry import RuleRegistry
from supervisor_control_tower.ui.components import page_header


DECISION_ROWS = [
    {
        "Decision": "Ready",
        "Technical verdict": "PASS",
        "Meaning": "Mandatory controls passed, no critical risk was identified and assurance meets the agent's ready threshold.",
        "Expected action": "Proceed to the next controlled approval or release stage.",
    },
    {
        "Decision": "Needs Review",
        "Technical verdict": "WARNING",
        "Meaning": "The output is usable only after a person reviews missing evidence, material control gaps, governance dependencies or a medium assurance score.",
        "Expected action": "Resolve the identified gaps and rerun the evaluation.",
    },
    {
        "Decision": "Blocked",
        "Technical verdict": "FAIL",
        "Meaning": "A critical control failed, the Judge blocked the output, governance blocked promotion or assurance is below the minimum threshold.",
        "Expected action": "Stop downstream use until the critical issue is resolved and reevaluated.",
    },
]

GLOSSARY_TERMS = [
    ("Agent Definition", "The versioned configuration describing an agent's purpose, ownership, capabilities, supported data, routing signals, rule pack and Judge rubric."),
    ("Agent Registry", "The runtime library of enabled agent definitions loaded from config/agents.json. It allows new configuration-only agents to appear without changing orchestrator routing code."),
    ("Capability-based Routing", "Automatic selection of the best agent by comparing source system, record type and available payload keys with each registered agent profile."),
    ("Routing Confidence", "The Supervisor's confidence that the selected agent is the correct evaluator for the submitted record."),
    ("Rule Pack", "A group of deterministic controls associated with an agent. Rule packs can be implemented in Python for complex logic or in JSON for configuration-only agents."),
    ("Deterministic Control", "A repeatable validation with an explicit pass or fail outcome, severity, evidence, message and control tag."),
    ("Mandatory Evidence", "Information that must be available before an output can be promoted. Missing mandatory evidence forces human review and caps assurance."),
    ("LLM-as-a-Judge", "A second evaluation layer that reviews grounding, completeness, consistency, safety, actionability and the agent-specific rubric."),
    ("Quality Dimensions", "Judge scores for evidence grounding, completeness, consistency, safety and actionability that contribute to the assurance calculation."),
    ("AI Assurance Score", "An explainable governance score from 0 to 100%. It combines deterministic controls, Judge confidence, quality dimensions, completeness and routing confidence. It is not a calibrated probability."),
    ("Disagreement Detection", "A safeguard triggered when deterministic controls and the LLM Judge reach materially conflicting conclusions."),
    ("Context Layer", "Business policies, risk considerations, ownership and dependencies supplied to the evaluation process."),
    ("Memory Layer", "Relevant prior evaluations used as transparent references for consistency and trend awareness; previous decisions do not override current evidence."),
    ("Governance Assessment", "Dependency and approval checks that can require review or block promotion even when the agent output is technically sound."),
    ("Remediation Proposal", "An advisory, approval-ready action plan. The Excel-first release never performs external write-back or changes an enterprise system."),
    ("Degraded Mode", "A controlled fallback used when the live LLM is unavailable. Deterministic controls continue, but the assurance score is capped."),
    ("Success Tag", "The classification recorded when an agent output passes without a more important finding tag."),
    ("Escalation Policy", "The configured owner who should review critical or high-severity findings for a specific agent."),
]


def _load_library(settings: Settings) -> tuple[list[AgentDefinition], RuleRegistry]:
    agent_registry = AgentRegistry.from_json(settings.resolve_path(settings.agent_config_path))
    rule_registry = RuleRegistry.from_json(
        agent_registry,
        settings.resolve_path(settings.rule_config_path),
    )
    return agent_registry.list_enabled(), rule_registry


def _render_list(title: str, items: Iterable[str], empty_message: str = "Not specified") -> None:
    values = [str(item) for item in items if str(item).strip()]
    st.markdown(f"**{title}**")
    if not values:
        st.caption(empty_message)
        return
    for item in values:
        st.markdown(f"- {item}")


def _render_agent_header(agent: AgentDefinition, rule_count: int) -> None:
    short_name = agent.labels.get("short_name") or agent.name
    business_owner = agent.labels.get("business_owner") or agent.owner
    st.markdown(
        f"""
        <div class="sup-card sup-agent-hero">
          <div>
            <span class="sup-badge">{html.escape(agent.lifecycle_status)}</span>
            <span class="sup-badge sup-badge-neutral">Version {html.escape(agent.version)}</span>
          </div>
          <h2 style="margin:14px 0 6px;font-size:26px;">{html.escape(short_name)}</h2>
          <p class="sup-body" style="font-size:15px;margin:0;">{html.escape(agent.description)}</p>
          <div class="sup-agent-meta">
            <span><strong>Business area:</strong> {html.escape(business_owner)}</span>
            <span><strong>Technical owner:</strong> {html.escape(agent.owner)}</span>
            <span><strong>Controls:</strong> {rule_count}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_agent_profile(agent: AgentDefinition, rules: list[Rule]) -> None:
    _render_agent_header(agent, len(rules))

    st.markdown("### 1. Purpose and business value")
    st.markdown(agent.glossary.business_purpose or agent.description)
    left, middle, right = st.columns(3)
    with left:
        _render_list("Business outcomes", agent.glossary.business_outcomes)
    with middle:
        _render_list("Common use cases", agent.glossary.example_use_cases)
    with right:
        _render_list("Typical outputs", agent.glossary.typical_outputs)

    st.markdown("### 2. Inputs and automatic routing")
    input_left, input_middle, input_right = st.columns(3)
    with input_left:
        _render_list("Typical inputs", agent.glossary.typical_inputs)
        _render_list("Required evidence", [humanize_identifier(item) for item in agent.required_evidence])
    with input_middle:
        _render_list("Supported source systems", [humanize_identifier(item) for item in agent.source_systems])
        _render_list("Supported task types", [humanize_identifier(item) for item in agent.supported_task_types])
    with input_right:
        _render_list("Routing evidence keys", [humanize_identifier(item) for item in agent.routing_key_hints])
        st.markdown("**Routing rule**")
        st.caption(
            "The Orchestrator selects this agent automatically when the source system, "
            "record type and payload evidence best match this profile. The user cannot "
            "manually override the selected agent."
        )

    st.markdown("### 3. What the Supervisor validates")
    st.markdown("**Deterministic controls**")
    control_rows = [
        {
            "Code": rule.code,
            "Control": rule.name,
            "Severity": rule.severity.value.title(),
            "Mandatory": "Yes" if rule.mandatory else "No",
            "Control objective": rule.description,
            "Finding tag": rule.tag,
        }
        for rule in rules
    ]
    st.dataframe(
        pd.DataFrame(control_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Code": st.column_config.TextColumn(width="small"),
            "Control": st.column_config.TextColumn(width="medium"),
            "Severity": st.column_config.TextColumn(width="small"),
            "Mandatory": st.column_config.TextColumn(width="small"),
            "Control objective": st.column_config.TextColumn(width="large"),
            "Finding tag": st.column_config.TextColumn(width="medium"),
        },
    )

    judge_left, threshold_right = st.columns([1.35, 1])
    with judge_left:
        _render_list("LLM-as-a-Judge rubric", agent.judge_rubric)
    with threshold_right:
        st.markdown("**Decision thresholds**")
        threshold_rows = [
            {"Threshold": "Minimum routing confidence", "Value": f"{agent.thresholds.routing_minimum:.0%}"},
            {"Threshold": "Minimum routing lead over next agent", "Value": f"{agent.thresholds.routing_margin:.0%}"},
            {"Threshold": "Ready assurance", "Value": f"{agent.thresholds.ready_assurance:.0%}"},
            {"Threshold": "Minimum assurance", "Value": f"{agent.thresholds.minimum_assurance:.0%}"},
            {"Threshold": "Missing-evidence score cap", "Value": f"{agent.thresholds.missing_evidence_cap:.0%}"},
        ]
        st.dataframe(pd.DataFrame(threshold_rows), use_container_width=True, hide_index=True)
        st.caption("A critical deterministic failure can still block the output regardless of the numeric score.")

    st.markdown("### 4. Human governance and boundaries")
    gov_left, gov_middle, gov_right = st.columns(3)
    with gov_left:
        _render_list("Human review triggers", agent.glossary.human_review_triggers)
    with gov_middle:
        escalation_items = [
            f"{humanize_identifier(severity)} findings → {owner}"
            for severity, owner in agent.escalation_policy.items()
        ]
        _render_list("Escalation path", escalation_items)
        _render_list("Operating notes", agent.glossary.operating_notes)
    with gov_right:
        _render_list("Out of scope", agent.glossary.out_of_scope)

    with st.expander("Technical identifiers and onboarding contract"):
        technical_rows = [
            {"Property": "Agent code", "Value": agent.code},
            {"Property": "Tool code", "Value": agent.tool_code},
            {"Property": "Rule pack", "Value": agent.rule_pack_id},
            {"Property": "Plugin", "Value": agent.plugin or "Configuration-only generic tool"},
            {"Property": "Success tag", "Value": agent.success_tag},
            {"Property": "Record types", "Value": ", ".join(agent.record_types)},
            {"Property": "Capabilities", "Value": ", ".join(agent.capabilities)},
        ]
        st.dataframe(pd.DataFrame(technical_rows), use_container_width=True, hide_index=True)
        st.caption(
            "A new configuration-only agent is onboarded by adding an agent definition and a rule pack. "
            "A custom Python plugin is required only when the domain needs complex calculations or cross-field logic."
        )


def _render_supervision_model(settings: Settings) -> None:
    st.subheader("End-to-end supervision flow")
    steps = [
        ("1", "Normalize", "Convert the selected enterprise record into one consistent payload and metadata structure."),
        ("2", "Route", "Rank registered agents using source system, record type and payload evidence."),
        ("3", "Apply context", "Load business policies, dependencies, ownership and relevant prior evaluations."),
        ("4", "Run controls", "Execute deterministic, severity-based rules from the selected agent's rule pack."),
        ("5", "Judge", "Use the LLM-as-a-Judge to assess grounding, completeness, safety and domain-specific quality."),
        ("6", "Synthesize", "Calculate assurance, detect disagreement and produce Ready, Needs Review or Blocked."),
        ("7", "Audit", "Persist routing, controls, Judge evidence, decision and advisory remediation to Excel."),
    ]
    for start in range(0, len(steps), 4):
        columns = st.columns(min(4, len(steps) - start))
        for column, (number, title, body) in zip(columns, steps[start : start + 4]):
            with column:
                st.markdown(
                    f"""
                    <div class="sup-flow-step">
                      <div class="sup-flow-number">{number}</div>
                      <div style="font-weight:750;margin-bottom:6px;">{html.escape(title)}</div>
                      <div class="sup-small" style="line-height:1.55;">{html.escape(body)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.subheader("AI Assurance Score")
    st.info(
        "The AI Assurance Score is an explainable governance score, not the probability that the agent is correct. "
        "It summarizes the strength of controls and evidence used for the decision."
    )
    score_rows = [
        {"Component": "Severity-weighted deterministic controls", "Weight": "30%", "What it represents": "Whether important controls passed, with critical and high findings carrying more weight."},
        {"Component": "LLM Judge confidence", "Weight": "25%", "What it represents": "The Judge's confidence in its structured review."},
        {"Component": "Judge quality dimensions", "Weight": "20%", "What it represents": "Grounding, completeness, consistency, safety and actionability."},
        {"Component": "Data completeness", "Weight": "15%", "What it represents": "Availability of required evidence and identity fields."},
        {"Component": "Routing confidence", "Weight": "10%", "What it represents": "Confidence that the record was evaluated by the correct agent."},
    ]
    st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

    guardrail_rows = [
        {"Guardrail": "Critical control failure", "Effect": f"Final assurance is capped at {settings.critical_failure_score_cap:.0%} and the decision is Blocked."},
        {"Guardrail": "LLM degraded mode", "Effect": f"Final assurance is capped at {settings.degraded_mode_score_cap:.0%}."},
        {"Guardrail": "Rules–Judge disagreement", "Effect": f"A {settings.disagreement_penalty:.0%} penalty is applied and the conflict is exposed for review."},
        {"Guardrail": "Missing mandatory evidence", "Effect": "Assurance is capped by the selected agent profile and the decision cannot be Ready."},
        {"Guardrail": "External write-back", "Effect": "Disabled. Remediation is advisory and requires explicit human action."},
    ]
    st.dataframe(pd.DataFrame(guardrail_rows), use_container_width=True, hide_index=True)


def _render_terms_and_decisions() -> None:
    st.subheader("Business decision definitions")
    st.dataframe(pd.DataFrame(DECISION_ROWS), use_container_width=True, hide_index=True)

    st.subheader("Core terminology")
    search = st.text_input(
        "Search glossary terms",
        placeholder="Example: assurance, routing, rule pack, degraded mode",
        key="glossary_term_search",
    ).strip().lower()
    matching = [
        (term, definition)
        for term, definition in GLOSSARY_TERMS
        if not search or search in term.lower() or search in definition.lower()
    ]
    if not matching:
        st.info("No glossary term matches the current search.")
        return
    for term, definition in matching:
        with st.expander(term):
            st.write(definition)


def render() -> None:
    settings = get_settings()
    agents, rule_registry = _load_library(settings)
    rules_by_agent = {
        agent.code: rule_registry.get_rules(agent.rule_pack_id, agent.tool_code)
        for agent in agents
    }

    page_header(
        "Agent glossary",
        "A detailed business and technical reference for every registered AI agent, its evidence, controls, decision model and operating boundaries.",
    )

    st.markdown(
        """
        <div class="sup-card" style="margin-bottom:18px;">
          <div class="sup-label">How to use this page</div>
          <p class="sup-body" style="margin-bottom:0;">
            Start with the Agent Library to understand what each agent does and what evidence it needs. 
            Use How Supervision Works for the common routing, validation and assurance model. 
            Use Terms & Decisions when a business or technical term needs clarification.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    unique_capabilities = {capability for agent in agents for capability in agent.capabilities}
    all_rules = [rule for rules in rules_by_agent.values() for rule in rules]
    metrics = st.columns(4)
    metrics[0].metric("Registered agents", len(agents))
    metrics[1].metric("Business capabilities", len(unique_capabilities))
    metrics[2].metric("Deterministic controls", len(all_rules))
    metrics[3].metric("External write-back", "Disabled")

    library_tab, model_tab, terms_tab = st.tabs(
        ["Agent Library", "How Supervision Works", "Terms & Decisions"]
    )

    with library_tab:
        st.subheader("Registered agent overview")
        filter_left, filter_right = st.columns([1.5, 1])
        with filter_left:
            search = st.text_input(
                "Search agents",
                placeholder="Search by agent, capability, owner, source system or use case",
                key="agent_glossary_search",
            )
        lifecycle_options = sorted({agent.lifecycle_status for agent in agents})
        with filter_right:
            lifecycle_filter = st.multiselect(
                "Lifecycle stage",
                lifecycle_options,
                placeholder="All stages",
            )

        visible_agents = filter_agents(agents, search, lifecycle_filter)
        if not visible_agents:
            st.info("No registered agent matches the selected filters.")
        else:
            summary_rows = [
                agent_summary_row(agent, rules_by_agent[agent.code])
                for agent in visible_agents
            ]
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Agent": st.column_config.TextColumn(width="medium"),
                    "Purpose": st.column_config.TextColumn(width="large"),
                    "Owner": st.column_config.TextColumn(width="medium"),
                    "Sources": st.column_config.TextColumn(width="large"),
                },
            )

            st.subheader("Detailed agent profile")
            selected_code = st.selectbox(
                "Choose an agent",
                options=[agent.code for agent in visible_agents],
                format_func=lambda code: next(
                    agent.name for agent in visible_agents if agent.code == code
                ),
                key="glossary_selected_agent",
            )
            selected_agent = next(
                agent for agent in visible_agents if agent.code == selected_code
            )
            _render_agent_profile(selected_agent, rules_by_agent[selected_agent.code])

            st.subheader("All agent profiles")
            st.caption("Open any profile below for a quick comparison without changing the selected detailed view.")
            for agent in visible_agents:
                with st.expander(f"{agent.name} · {agent.lifecycle_status} · {len(rules_by_agent[agent.code])} controls"):
                    st.write(agent.glossary.business_purpose or agent.description)
                    quick_left, quick_middle, quick_right = st.columns(3)
                    with quick_left:
                        _render_list("Business outcomes", agent.glossary.business_outcomes)
                    with quick_middle:
                        _render_list("Required evidence", [humanize_identifier(item) for item in agent.required_evidence])
                    with quick_right:
                        _render_list("Human review triggers", agent.glossary.human_review_triggers)

    with model_tab:
        _render_supervision_model(settings)

    with terms_tab:
        _render_terms_and_decisions()
