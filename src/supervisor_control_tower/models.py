from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class AgentCode(StrEnum):
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


TOOL_TO_AGENT: dict[ToolCode, AgentCode] = {
    ToolCode.PIPELINE: AgentCode.PIPELINE_TROUBLESHOOTING,
    ToolCode.INFRA: AgentCode.INFRA_PROVISIONING,
    ToolCode.FINOPS: AgentCode.FINOPS_OPTIMIZATION,
    ToolCode.PROJECT: AgentCode.PROJECT_MANAGEMENT,
}

AGENT_TO_TOOL: dict[AgentCode, ToolCode] = {v: k for k, v in TOOL_TO_AGENT.items()}


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
    expected_agent_code: AgentCode | None = None

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
    comments: str | None = None


class RoutingDecision(BaseModel):
    selected_tool: ToolCode
    detected_agent_code: AgentCode
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("detected_agent_code")
    @classmethod
    def tool_agent_match(cls, value: AgentCode, info: Any) -> AgentCode:
        tool = info.data.get("selected_tool")
        if tool and TOOL_TO_AGENT[tool] != value:
            raise ValueError("selected tool and detected agent do not match")
        return value


class RuleResultModel(BaseModel):
    rule_code: str
    rule_name: str
    severity: Severity
    passed: bool
    evidence: dict[str, Any] = Field(default_factory=dict)
    message: str
    tag: str


class ToolResult(BaseModel):
    tool_code: ToolCode
    agent_code: AgentCode
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


class LlmJudgementResult(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    # Enhanced LLM-powered fields
    analysis: str = ""          # 2-4 sentence narrative of what the agent did and overall assessment
    findings: list[JudgeFinding] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)  # [{priority, action}]
    quality_dimensions: dict[str, float] = Field(default_factory=dict)   # evidence_quality, completeness, safety, accuracy
    focus_area_addressed: bool = True
    raw_response: dict[str, Any] = Field(default_factory=dict)


class FinalSynthesis(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    primary_tag: str
    findings_summary: list[str] = Field(default_factory=list)
    data_completeness: float = Field(ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class ValidationRunResult(BaseModel):
    run_id: str
    record: NormalizedRecord
    routing: RoutingDecision
    tool_result: ToolResult
    llm_judgement: LlmJudgementResult
    final: FinalSynthesis
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    initiated_by: str
