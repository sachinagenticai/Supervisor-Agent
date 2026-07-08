from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from supervisor_control_tower.models import NormalizedRecord, RuleResultModel, Severity, ToolCode

RuleEvaluator = Callable[[NormalizedRecord], tuple[bool, dict[str, Any], str]]


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    description: str
    severity: Severity
    tool_code: ToolCode
    evaluator: RuleEvaluator
    failure_message: str
    tag: str


class RuleEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def run(self, record: NormalizedRecord, tool_code: ToolCode) -> list[RuleResultModel]:
        results: list[RuleResultModel] = []
        for rule in [r for r in self.rules if r.tool_code == tool_code]:
            try:
                passed, evidence, success_message = rule.evaluator(record)
                message = success_message if passed else rule.failure_message
            except Exception as exc:
                passed = False
                evidence = {"exception_type": exc.__class__.__name__}
                message = f"Rule could not be evaluated safely: {rule.failure_message}"
            results.append(
                RuleResultModel(
                    rule_code=rule.code,
                    rule_name=rule.name,
                    severity=rule.severity,
                    passed=passed,
                    evidence=evidence,
                    message=message,
                    tag=rule.tag,
                )
            )
        return results


def exists(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def get(record: NormalizedRecord, key: str, default: Any = None) -> Any:
    if key.startswith("metadata."):
        root: Any = record.metadata
        parts = key.split(".")[1:]
    elif key.startswith("payload."):
        root = record.payload
        parts = key.split(".")[1:]
    else:
        root = record.payload
        parts = key.split(".")
    for part in parts:
        if isinstance(root, dict):
            root = root.get(part, default)
        else:
            return default
    return root


def field_exists(field: str) -> RuleEvaluator:
    def evaluate(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
        value = get(record, field)
        return exists(value), {"field": field, "present": exists(value)}, f"{field} is present."
    return evaluate


def text_contains_any(text: str, candidates: list[str]) -> bool:
    lowered = text.lower()
    return any(c.lower() in lowered for c in candidates)


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{k}: {flatten_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "\n".join(flatten_text(v) for v in value)
    return str(value)


SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----"),
]

UNSAFE_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/(\s|$)"),
    re.compile(r"\bchmod\s+777\b"),
    re.compile(r"\bcurl\b.+\|\s*(sh|bash)\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
]


def no_secret_exposure(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
    text = flatten_text(record.payload)
    matched = [p.pattern for p in SECRET_PATTERNS if p.search(text)]
    return not matched, {"patterns_found": len(matched)}, "No obvious secrets were detected."


def no_unsafe_shell_command(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
    text = flatten_text(record.payload)
    matched = [p.pattern for p in UNSAFE_COMMAND_PATTERNS if p.search(text)]
    return not matched, {"patterns_found": len(matched)}, "No obvious unsafe shell command was detected."


def confidence_in_range(field: str = "confidence") -> RuleEvaluator:
    def evaluate(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
        value = get(record, field)
        ok = isinstance(value, (int, float)) and 0 <= float(value) <= 1
        return ok, {"field": field, "value": value}, "Confidence is within the accepted 0 to 1 range."
    return evaluate


def list_has_items(field: str) -> RuleEvaluator:
    def evaluate(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
        value = get(record, field)
        ok = isinstance(value, list) and len(value) > 0
        return ok, {"field": field, "count": len(value) if isinstance(value, list) else 0}, f"{field} contains one or more entries."
    return evaluate
