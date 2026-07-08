"""LLM client for the Supervisor Agent Control Tower.

Two backends, selected by config:
  1. MOCK_LLM=true  → deterministic mock (no network, safe for demos)
  2. MOCK_LLM=false → standard OpenAI API (requires OPENAI_API_KEY)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from supervisor_control_tower.config import Settings
from supervisor_control_tower.models import Severity, Verdict

logger = logging.getLogger(__name__)


class LlmUnavailableError(RuntimeError):
    pass


class LlmJsonClient:
    """Unified LLM client. Callers always call `complete_json(system, payload)`.

    Backend is selected at construction:
      mock   → _mock_response()   (deterministic, no network)
      openai → standard OpenAI API
    """

    # Models that reject a custom temperature (only default=1 accepted).
    _NO_TEMP_MODELS = ("o1", "o3", "o4", "gpt-5")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._openai_client: Any = None

        if settings.mock_llm:
            self._backend = "mock"
            self.model_name = "mock"
            return

        if not settings.openai_api_key:
            raise LlmUnavailableError(
                "OPENAI_API_KEY is not set. "
                "Add it to .env or set MOCK_LLM=true for demo mode."
            )

        from openai import OpenAI

        client_kwargs: dict[str, Any] = {
            "api_key": settings.openai_api_key,
            "timeout": settings.llm_timeout_seconds,
        }

        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url

        self._openai_client = OpenAI(**client_kwargs)

        self._backend = "openai"
        self.model_name = settings.llm_model
        logger.info("LLM backend: OpenAI (%s)", settings.llm_model)

    # ── Public API ────────────────────────────────────────────────────────────

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if self._backend == "mock":
            return self._mock_response(user_payload)
        return self._openai_complete(system_prompt, user_payload)

    # ── OpenAI backend ────────────────────────────────────────────────────────

    def _supports_temperature(self) -> bool:
        return not any(self.model_name.startswith(p) for p in self._NO_TEMP_MODELS)

    def _openai_complete(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        assert self._openai_client is not None
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, default=str)},
            ],
            "timeout": self.settings.llm_timeout_seconds,
            "response_format": {"type": "json_object"},
        }
        if self._supports_temperature():
            kwargs["temperature"] = 0.1
        response = self._openai_client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    # ── Mock backend ──────────────────────────────────────────────────────────

    def _mock_response(self, user_payload: dict[str, Any]) -> dict[str, Any]:
        deterministic_findings = user_payload.get("deterministic_findings", [])
        failed = [f for f in deterministic_findings if not f.get("passed", True)]
        severities = {str(f.get("severity")) for f in failed}
        if "CRITICAL" in severities:
            verdict, confidence = Verdict.FAIL.value, 0.88
            reason = "Mock judge found critical deterministic issues that make the record unsafe or incomplete."
        elif severities.intersection({"HIGH", "MEDIUM"}):
            verdict, confidence = Verdict.WARNING.value, 0.74
            reason = "Mock judge found material deterministic warnings that need review."
        else:
            verdict, confidence = Verdict.PASS.value, 0.91
            reason = "Mock judge found the output supported by the available evidence."
        first_failed = failed[0] if failed else {}
        findings = []
        if first_failed:
            findings.append({
                "severity": first_failed.get("severity", Severity.LOW.value),
                "tag": first_failed.get("tag", "QUALITY"),
                "message": first_failed.get("message", "Review deterministic finding."),
            })
        return {
            "verdict": verdict,
            "confidence": confidence,
            "reason": reason,
            "findings": findings,
            "focus_area_addressed": True,
        }

