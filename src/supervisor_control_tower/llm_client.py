"""Structured JSON client for mock mode and the standard OpenAI API."""
from __future__ import annotations

import json
import logging
from typing import Any

from supervisor_control_tower.config import Settings
from supervisor_control_tower.models import Severity, Verdict

logger = logging.getLogger(__name__)


class LlmUnavailableError(RuntimeError):
    """Raised when the configured LLM cannot return a usable response."""


class LlmJsonClient:
    """Return JSON objects from either the deterministic mock or OpenAI.

    The standard OpenAI client provides timeout and retry handling. The model is
    instructed to return JSON and the API response format is constrained to a
    JSON object. No Azure OpenAI or custom endpoint path is present.
    """

    _NO_TEMPERATURE_MODELS = ("o1", "o3", "o4", "gpt-5")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._openai_client: Any = None

        if settings.mock_llm:
            self._backend = "mock"
            self.model_name = "mock-enterprise-judge"
        else:
            self._backend = "openai"
            self.model_name = settings.llm_model
            self._initialize_openai()

        logger.info("LLM backend selected: %s (%s)", self._backend, self.model_name)

    def _initialize_openai(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LlmUnavailableError(
                "The openai package is required when MOCK_LLM=false."
            ) from exc

        self._openai_client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=float(self.settings.llm_timeout_seconds),
            max_retries=self.settings.llm_max_retries,
        )

    @property
    def backend(self) -> str:
        return self._backend

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if self._backend == "mock":
            return self._mock_response(user_payload)
        return self._openai_complete(system_prompt, user_payload)

    def _supports_temperature(self) -> bool:
        model = self.model_name.lower()
        return not any(model.startswith(prefix) for prefix in self._NO_TEMPERATURE_MODELS)

    def _openai_complete(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if self._openai_client is None:
            raise LlmUnavailableError("OpenAI client is not initialized.")

        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, default=str, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        if self._supports_temperature():
            request["temperature"] = 0.1

        try:
            response = self._openai_client.chat.completions.create(**request)
            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI returned an empty message")
            result = json.loads(content)
            request_id = getattr(response, "_request_id", None)
            if request_id:
                logger.debug("OpenAI request completed: request_id=%s", request_id)
        except Exception as exc:
            request_id = getattr(exc, "request_id", None)
            logger.warning(
                "OpenAI request failed: error_type=%s request_id=%s",
                exc.__class__.__name__,
                request_id or "unavailable",
            )
            raise LlmUnavailableError(
                f"OpenAI request failed: {exc.__class__.__name__}"
            ) from exc

        if not isinstance(result, dict):
            raise LlmUnavailableError("OpenAI returned JSON that was not an object.")
        return result

    def _mock_response(self, user_payload: dict[str, Any]) -> dict[str, Any]:
        if user_payload.get("task") == "route_record" or "allowed_agents" in user_payload:
            candidates = user_payload.get("deterministic_candidates") or []
            if candidates:
                best = max(candidates, key=lambda item: float(item.get("score", 0.0)))
                confidence = max(0.68, min(0.95, float(best.get("score", 0.68)) + 0.08))
                return {
                    "detected_agent_code": best.get("agent_code"),
                    "confidence": confidence,
                    "reason": "Mock router selected the highest configured capability match.",
                }
            allowed = user_payload.get("allowed_agents") or []
            if not allowed:
                raise LlmUnavailableError("No agents were supplied to the mock router.")
            return {
                "detected_agent_code": allowed[0]["code"],
                "confidence": 0.70,
                "reason": "Mock router selected the first enabled agent because no deterministic candidate was available.",
            }

        deterministic_findings = user_payload.get("deterministic_findings", [])
        failed = [finding for finding in deterministic_findings if not finding.get("passed", True)]
        severities = {str(finding.get("severity")) for finding in failed}
        critical = "CRITICAL" in severities
        material = bool(severities.intersection({"HIGH", "MEDIUM"}))
        if critical:
            verdict, confidence = Verdict.FAIL.value, 0.86
            reason = "Critical deterministic controls found unsafe or materially unsupported output."
            dimensions = {
                "evidence_quality": 0.48,
                "completeness": 0.55,
                "consistency": 0.52,
                "safety": 0.20,
                "accuracy": 0.50,
                "actionability": 0.62,
            }
        elif material:
            verdict, confidence = Verdict.WARNING.value, 0.76
            reason = "Material evidence or completeness gaps require human review."
            dimensions = {
                "evidence_quality": 0.64,
                "completeness": 0.68,
                "consistency": 0.72,
                "safety": 0.92,
                "accuracy": 0.71,
                "actionability": 0.75,
            }
        else:
            verdict, confidence = Verdict.PASS.value, 0.91
            reason = "The output is supported by available evidence and no critical risk was identified."
            dimensions = {
                "evidence_quality": 0.88,
                "completeness": 0.90,
                "consistency": 0.91,
                "safety": 0.96,
                "accuracy": 0.89,
                "actionability": 0.87,
            }

        findings = [
            {
                "severity": finding.get("severity", Severity.LOW.value),
                "tag": finding.get("tag", "QUALITY"),
                "message": finding.get("message", "Review deterministic finding."),
                "evidence_references": [finding.get("rule_code", "deterministic-rule")],
            }
            for finding in failed[:4]
        ]
        recommendations = [
            {
                "priority": finding.get("severity", Severity.MEDIUM.value),
                "action": f"Resolve {finding.get('rule_name', 'the failed control')}: {finding.get('message', '')}",
                "owner": None,
            }
            for finding in failed[:3]
        ]
        if not recommendations:
            recommendations = [
                {
                    "priority": Severity.INFO.value,
                    "action": "Retain the evaluation evidence and proceed through the normal approval workflow.",
                    "owner": None,
                }
            ]
        return {
            "verdict": verdict,
            "confidence": confidence,
            "reason": reason,
            "analysis": (
                "The mock enterprise judge reviewed the complete record, deterministic controls, business context "
                "and prior evaluation memory. The result is intentionally deterministic for repeatable demos."
            ),
            "quality_dimensions": dimensions,
            "findings": findings,
            "recommendations": recommendations,
        }
