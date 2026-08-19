from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentCode(StrEnum):
    """Known built-in agent codes.

    Runtime models deliberately use strings so new agents can be added through
    configuration without changing this enum. The enum remains as a convenience
    for built-in plugins and backwards-compatible tests.
    """

    PIPELINE_TROUBLESHOOTING = "PIPELINE_TROUBLESHOOTING"
    INFRA_PROVISIONING = "INFRA_PROVISIONING"
    FINOPS_OPTIMIZATION = "FINOPS_OPTIMIZATION"
    PROJECT_MANAGEMENT = "PROJECT_MANAGEMENT"


class ToolCode(StrEnum):
    PIPELINE = "pipeline_troubleshooting_tool"
    INFRA = "infrastructure_provisioning_tool"
    FINOPS = "finops_optimization_tool"
    PROJECT = "project_management_tool"


class Verdict(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class BusinessDecision(StrEnum):
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class AssuranceBand(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExecutionStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AgentThresholds(BaseModel):
    routing_minimum: float = Field(default=0.62, ge=0.0, le=1.0)
    routing_margin: float = Field(default=0.08, ge=0.0, le=1.0)
    ready_assurance: float = Field(default=0.80, ge=0.0, le=1.0)
    minimum_assurance: float = Field(default=0.60, ge=0.0, le=1.0)
    missing_evidence_cap: float = Field(default=0.60, ge=0.0, le=1.0)


class AgentGlossary(BaseModel):
    """Business-facing documentation displayed by the Agent Glossary page.

    Keeping this content inside the agent definition ensures that a newly
    onboarded configuration-only agent automatically appears in the UI without
    adding page-specific Python code.
    """

    business_purpose: str = Field(default="", max_length=2000)
    business_outcomes: list[str] = Field(default_factory=list)
    example_use_cases: list[str] = Field(default_factory=list)
    typical_inputs: list[str] = Field(default_factory=list)
    typical_outputs: list[str] = Field(default_factory=list)
    human_review_triggers: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    operating_notes: list[str] = Field(default_factory=list)

    @field_validator(
        "business_outcomes",
        "example_use_cases",
        "typical_inputs",
        "typical_outputs",
        "human_review_triggers",
        "out_of_scope",
        "operating_notes",
        mode="before",
    )
    @classmethod
    def normalize_glossary_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a list of strings")
        return [str(item).strip() for item in value if str(item).strip()]


class AgentDefinition(BaseModel):
    code: str = Field(min_length=2, max_length=100, pattern=r"^[A-Z][A-Z0-9_]+$")
    name: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=10, max_length=1000)
    version: str = Field(default="1.0.0", min_length=1, max_length=30)
    owner: str = Field(default="AI Platform Team", min_length=2, max_length=200)
    enabled: bool = True
    lifecycle_status: str = Field(default="POC", max_length=40)
    capabilities: list[str] = Field(default_factory=list)
    supported_task_types: list[str] = Field(default_factory=list)
    source_systems: list[str] = Field(default_factory=list)
    record_types: list[str] = Field(default_factory=list)
    routing_key_hints: list[str] = Field(default_factory=list)
    rule_pack_id: str = Field(min_length=2, max_length=100)
    tool_code: str = Field(min_length=2, max_length=100)
    plugin: str | None = Field(default=None, max_length=100)
    judge_rubric: list[str] = Field(default_factory=list)
    success_tag: str = Field(default="VALIDATED", min_length=2, max_length=100)
    thresholds: AgentThresholds = Field(default_factory=AgentThresholds)
    required_evidence: list[str] = Field(default_factory=list)
    escalation_policy: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    glossary: AgentGlossary = Field(default_factory=AgentGlossary)

    @field_validator(
        "capabilities",
        "supported_task_types",
        "source_systems",
        "record_types",
        "routing_key_hints",
        "judge_rubric",
        "required_evidence",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a list of strings")
        return [str(item).strip() for item in value if str(item).strip()]


class AppUser(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    google_subject_id: str
    email: str
    display_name: str
    profile_image_url: str | None = None


class ValidationRecordSummary(BaseModel):
    id: str
    external_reference: str
    record_title: str
    source_system: str
    record_type: str
    expected_agent_code: str | None = None

    @property
    def dropdown_label(self) -> str:
        domain_hint = self.record_type.replace("_", " ").title()
        source_hint = self.source_system.replace("_", " ").title()
        return f"{self.external_reference} | {source_hint} / {domain_hint} | {self.record_title}"


class NormalizedRecord(BaseModel):
    record_id: str
    external_reference: str
    source_system: str
    record_type: str
    record_title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    comments: str | None = Field(default=None, max_length=2000)


class RoutingCandidate(BaseModel):
    agent_code: str
    tool_code: str
    score: float = Field(ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    selected_tool: str
    detected_agent_code: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    routing_method: str = "deterministic"
    candidates: list[RoutingCandidate] = Field(default_factory=list)


class RuleResultModel(BaseModel):
    rule_code: str
    rule_name: str
    severity: Severity
    passed: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    message: str
    tag: str
    mandatory: bool = False


class ToolResult(BaseModel):
    tool_code: str
    agent_code: str
    execution_success: bool = True
    summary: str
    rule_results: list[RuleResultModel] = Field(default_factory=list)
    derived_metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JudgeFinding(BaseModel):
    severity: Severity
    tag: str
    message: str
    evidence_references: list[str] = Field(default_factory=list)


class JudgeRecommendation(BaseModel):
    priority: Severity = Severity.MEDIUM
    action: str
    owner: str | None = None


class LlmJudgementResult(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    analysis: str = ""
    findings: list[JudgeFinding] = Field(default_factory=list)
    recommendations: list[JudgeRecommendation] = Field(default_factory=list)
    quality_dimensions: dict[str, float] = Field(default_factory=dict)
    focus_area_addressed: bool = True
    degraded_mode: bool = False
    raw_response: dict[str, Any] = Field(default_factory=dict)

    @field_validator("quality_dimensions")
    @classmethod
    def validate_quality_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return {str(k): min(1.0, max(0.0, float(v))) for k, v in value.items()}


class ContextSnapshot(BaseModel):
    global_policies: list[str] = Field(default_factory=list)
    agent_context: list[str] = Field(default_factory=list)
    record_context: dict[str, Any] = Field(default_factory=dict)


class MemoryReference(BaseModel):
    run_id: str
    external_reference: str
    agent_code: str
    decision: BusinessDecision
    assurance_score: float = Field(ge=0.0, le=1.0)
    primary_tag: str
    completed_at: str | None = None


class MemorySnapshot(BaseModel):
    references: list[MemoryReference] = Field(default_factory=list)
    summary: str = "No relevant previous evaluations were found."


class GovernanceAssessment(BaseModel):
    status: BusinessDecision = BusinessDecision.READY
    reasons: list[str] = Field(default_factory=list)
    dependency_results: list[dict[str, Any]] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)


class RemediationAction(BaseModel):
    priority: Severity
    action: str
    source: str
    approval_required: bool = True


class RemediationPlan(BaseModel):
    status: str = "PROPOSED"
    execution_enabled: bool = False
    actions: list[RemediationAction] = Field(default_factory=list)
    safety_note: str = (
        "Remediation is advisory only. No external system is changed without explicit human approval."
    )


class FinalSynthesis(BaseModel):
    verdict: Verdict
    business_decision: BusinessDecision
    assurance_score: float = Field(ge=0.0, le=1.0)
    assurance_band: AssuranceBand
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    primary_tag: str
    findings_summary: list[str] = Field(default_factory=list)
    recommended_action: str
    data_completeness: float = Field(ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    disagreement_detected: bool = False
    degraded_mode: bool = False
    governance: GovernanceAssessment = Field(default_factory=GovernanceAssessment)
    remediation: RemediationPlan = Field(default_factory=RemediationPlan)

    @model_validator(mode="after")
    def keep_confidence_aligned(self) -> "FinalSynthesis":
        if abs(self.confidence - self.assurance_score) > 0.001:
            self.confidence = self.assurance_score
        return self


class ValidationRunResult(BaseModel):
    run_id: str
    record: NormalizedRecord
    routing: RoutingDecision
    tool_result: ToolResult
    llm_judgement: LlmJudgementResult
    final: FinalSynthesis
    context: ContextSnapshot = Field(default_factory=ContextSnapshot)
    memory: MemorySnapshot = Field(default_factory=MemorySnapshot)
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    initiated_by: str
