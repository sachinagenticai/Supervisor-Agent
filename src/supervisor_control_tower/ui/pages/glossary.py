from __future__ import annotations

import streamlit as st

from supervisor_control_tower.ui.components import (
    page_caption, section_header, agent_accent, agent_initials, TOKENS
)


def render() -> None:
    st.title("Glossary & Capabilities")
    page_caption("What the Supervisor Agent Control Tower does, how it works, and what it does not do.")

    # ── Architecture overview ────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                    border-radius:14px; padding:22px; margin-bottom:20px;">
          <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em;
                      color:{TOKENS['muted']}; margin-bottom:6px;">Architecture</div>
          <p style="color:{TOKENS['text']}; font-size:14px; line-height:1.6; margin-top:0;">
            The Supervisor Agent Control Tower is a single Streamlit application that validates stored execution
            records from <strong>four AI agents</strong> using a deterministic rule engine, an LLM-as-a-Judge,
            and a final deterministic synthesizer. No external systems are mutated.
          </p>
          <div style="background:{TOKENS['bg']}; border:1px solid {TOKENS['border']}; border-radius:9px;
                      padding:12px 14px; font-family:monospace; font-size:12.5px; color:{TOKENS['text']};
                      line-height:1.7;">
            Selected Record → Supervisor Orchestrator → Auto-selected Tool Node → Rule Checks → LLM Judge → Final Synthesizer → Excel / PostgreSQL
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Core concepts ────────────────────────────────────────────────────
    section_header("Core Concepts")
    concepts = [
        ("Supervisor Orchestrator", "Inspects source system, record type, metadata, and payload keys to select exactly one specialised tool node. No manual agent/tool selection is required or allowed."),
        ("Four Specialised Tool Nodes", "Each agent has a corresponding tool: Pipeline, Infrastructure, FinOps, and Project Management. Each tool runs domain-specific deterministic rules against the selected record."),
        ("LLM Judge", "An Azure OpenAI model reviews nuanced quality, evidence alignment, and completeness that deterministic rules cannot fully assess. Returns a structured JSON verdict. All record content is treated as untrusted data."),
        ("Final Synthesizer", "A deterministic Python component that combines rule failures, LLM verdict, confidence scores, and data completeness into a single PASS/WARNING/FAIL verdict with a readable reason."),
        ("Confidence Scorecard", "A transparent weighted score combining: 30% rule pass ratio, 35% severity-weighted rule score, 25% LLM confidence, 10% data completeness."),
        ("Drift Detection", "Compares the earliest and latest halves of validation history per agent. Flags MEDIUM/HIGH alerts if failure rate rises ≥10% or confidence drops ≥12% in recent runs."),
        ("Production Readiness Score", "A 0–100 score per agent combining pass rate (70 pts), validation volume (10 pts), and lifecycle stage bonus (20 pts). Guides promotion decisions."),
        ("Excel Storage (POC)", "Persistence uses a local Excel workbook. The repository layer is decoupled — switching to PostgreSQL requires only a config change (STORAGE_BACKEND=postgres)."),
    ]
    cols = st.columns(2)
    for i, (title, body) in enumerate(concepts):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                            border-radius:12px; padding:14px 16px; margin-bottom:14px; min-height:118px;">
                  <div style="font-weight:700; color:{TOKENS['text']}; font-size:14px; margin-bottom:6px;">{title}</div>
                  <div style="color:{TOKENS['muted']}; font-size:13px; line-height:1.5;">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Verdict definitions ───────────────────────────────────────────────
    st.markdown("---")
    section_header("Verdict Definitions")
    _verdicts = [
        ("PASS", TOKENS["pass"], TOKENS["pass_soft"],
         "All mandatory rules passed. LLM Judge found the output evidence-supported. Confidence is above the high threshold (≥ 0.80)."),
        ("WARNING", TOKENS["warn"], TOKENS["warn_soft"],
         "High/Medium severity rule failures, LLM warning, or confidence between 0.60–0.80. Human review is recommended before promotion."),
        ("FAIL", TOKENS["fail"], TOKENS["fail_soft"],
         "Critical rule failure, LLM FAIL verdict, unsafe/unsupported content, or confidence below minimum threshold (< 0.60)."),
    ]
    vcols = st.columns(3)
    for col, (label, color, bg, desc) in zip(vcols, _verdicts):
        with col:
            st.markdown(
                f"""
                <div style="background:{bg}; border:1px solid {TOKENS['border']}; border-left:4px solid {color};
                            border-radius:12px; padding:16px 18px; min-height:150px;">
                  <div style="display:flex; align-items:center; gap:9px;">
                    <span style="width:10px; height:10px; border-radius:50%; background:{color};
                                 display:inline-block;"></span>
                    <span style="font-size:17px; font-weight:800; color:{color}; letter-spacing:0.02em;">{label}</span>
                  </div>
                  <div style="font-size:13px; color:{TOKENS['text']}; margin-top:10px; line-height:1.55;">{desc}</div>
                </div>
                """, unsafe_allow_html=True,
            )

    # ── Supervised agents ────────────────────────────────────────────────
    st.markdown("---")
    section_header("Supervised Agents")
    agents = [
        ("PIPELINE_TROUBLESHOOTING", "Pipeline Troubleshooting Agent", "UAT Testing",
         "Validates CI/CD failure RCA, log evidence, remediation safety, PR structure, notification quality, and post-fix consistency. "
         "MTTR −50%, RCA speed −75%, ~2 hrs/failure saved."),
        ("INFRA_PROVISIONING", "Infrastructure Provisioning Agent", "Development / UAT",
         "Validates design interpretation, generated Terraform/Bicep, naming, tagging, security baseline, environment mapping, "
         "approval, and PR structure. 6× faster provisioning; 65–70% effort reduction."),
        ("FINOPS_OPTIMIZATION", "InfraScaling & Cost Optimization Agent", "UAT Active",
         "Validates telemetry, billing, underutilisation evidence, savings estimates, visualisations, and query relevance. "
         "10–25% cloud cost reduction; 100% asset visibility; 40–60 hrs/month saved."),
        ("PROJECT_MANAGEMENT", "AI-Driven Project Management Agent", "POC",
         "Validates generated stories, acceptance criteria, sprint status, repo/deployment alignment, blocker evidence, "
         "velocity, capacity, and schedule risk. Sprint planning −30–40%; reporting overhead −25–50%."),
    ]
    for code, name, stage, desc in agents:
        accent = agent_accent(code)
        initials = agent_initials(code)
        st.markdown(
            f"""
            <div style="background:{TOKENS['surface']}; border:1px solid {TOKENS['border']};
                        border-left:4px solid {accent}; border-radius:12px; padding:16px 18px; margin-bottom:12px;">
              <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
                <span style="width:38px; height:38px; border-radius:10px; background:{accent}1a; color:{accent};
                             display:flex; align-items:center; justify-content:center; font-weight:800;
                             font-size:13px; letter-spacing:0.03em; flex:none;">{initials}</span>
                <div>
                  <div style="font-weight:700; color:{TOKENS['text']}; font-size:15px;">{name}</div>
                  <span style="background:{accent}14; color:{accent}; border-radius:999px; padding:2px 10px;
                               font-size:11px; font-weight:600;">{stage}</span>
                </div>
              </div>
              <div style="color:{TOKENS['muted']}; font-size:13px; line-height:1.55;">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── POC scope ────────────────────────────────────────────────────────
    st.markdown("---")
    section_header("POC Scope — What This Does NOT Do")
    st.info(
        "This is a **POC**. The following are explicitly out of scope and will not be implemented: "
        "live external connectors, real GitHub/Azure DevOps/Jira/Teams mutations, real PR creation, "
        "infrastructure deployment, resource deletion/stopping/resizing, streaming, background workers, "
        "schedulers, Kafka, queues, Redis, vector databases, Kubernetes, microservices, "
        "rule-authoring UI, supervisor-of-supervisor logic, multi-tenant RBAC."
    )

    st.markdown("---")
    st.caption("Supervisor Agent Control Tower · POC · Excel-backed · Azure OpenAI LLM Judge · Streamlit UI")
