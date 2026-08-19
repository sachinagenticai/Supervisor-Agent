from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from supervisor_control_tower.models import NormalizedRecord, RuleResultModel, Severity

RuleEvaluator = Callable[[NormalizedRecord], tuple[bool, dict[str, Any], str]]


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    description: str
    severity: Severity
    tool_code: str
    evaluator: RuleEvaluator
    failure_message: str
    tag: str
    mandatory: bool = False


class RuleEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = list(rules)

    def run(self, record: NormalizedRecord, tool_code: str) -> list[RuleResultModel]:
        results: list[RuleResultModel] = []
        for rule in [candidate for candidate in self.rules if str(candidate.tool_code) == str(tool_code)]:
            try:
                passed, evidence, success_message = rule.evaluator(record)
                message = success_message if passed else rule.failure_message
            except Exception as exc:  # fail closed while protecting sensitive exception details
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
                    mandatory=rule.mandatory,
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
        present = exists(value)
        return present, {"field": field, "present": present}, f"{field} is present."

    return evaluate


def text_contains_any(text: str, candidates: list[str]) -> bool:
    lowered = text.lower()
    return any(candidate.lower() in lowered for candidate in candidates)


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{key}: {flatten_text(child)}" for key, child in value.items())
    if isinstance(value, list):
        return "\n".join(flatten_text(child) for child in value)
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

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"bypass\s+(the\s+)?(policy|guardrail|validation)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+)?unrestricted", re.IGNORECASE),
]


def no_secret_exposure(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
    text = flatten_text(record.payload)
    matched = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    return not matched, {"patterns_found": len(matched)}, "No obvious secrets were detected."


def no_unsafe_shell_command(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
    text = flatten_text(record.payload)
    matched = [pattern.pattern for pattern in UNSAFE_COMMAND_PATTERNS if pattern.search(text)]
    return not matched, {"patterns_found": len(matched)}, "No obvious unsafe shell command was detected."


def no_prompt_injection(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
    text = flatten_text(record.payload)
    matched = [pattern.pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern.search(text)]
    return not matched, {"patterns_found": len(matched)}, "No prompt-injection pattern was detected."


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


def build_config_evaluator(definition: dict[str, Any]) -> RuleEvaluator:
    rule_type = str(definition.get("type", "")).strip().lower()
    field = str(definition.get("field", "")).strip()

    if rule_type == "required":
        return field_exists(field)

    if rule_type == "allowed_values":
        allowed = {str(value).strip().lower() for value in definition.get("values", [])}

        def allowed_values(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            value = get(record, field)
            normalized = str(value).strip().lower() if value is not None else ""
            ok = normalized in allowed
            return ok, {"field": field, "value": value, "allowed_values": sorted(allowed)}, f"{field} uses an approved value."

        return allowed_values

    if rule_type == "numeric_range":
        minimum = float(definition.get("minimum", float("-inf")))
        maximum = float(definition.get("maximum", float("inf")))

        def numeric_range(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            value = get(record, field)
            ok = isinstance(value, (int, float)) and minimum <= float(value) <= maximum
            return ok, {"field": field, "value": value, "minimum": minimum, "maximum": maximum}, f"{field} is within the accepted range."

        return numeric_range

    if rule_type == "list_min_items":
        minimum = int(definition.get("minimum", 1))

        def list_min_items(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            value = get(record, field)
            count = len(value) if isinstance(value, list) else 0
            return count >= minimum, {"field": field, "count": count, "minimum": minimum}, f"{field} contains sufficient evidence."

        return list_min_items

    if rule_type == "min_text_length":
        minimum = int(definition.get("minimum", 1))

        def min_text_length(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            value = str(get(record, field, "") or "").strip()
            return len(value) >= minimum, {"field": field, "length": len(value), "minimum": minimum}, f"{field} contains sufficient detail."

        return min_text_length

    if rule_type == "forbidden_text":
        patterns = [str(pattern).lower() for pattern in definition.get("patterns", [])]

        def forbidden_text(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            value = flatten_text(get(record, field, "")).lower()
            matched = [pattern for pattern in patterns if pattern and pattern in value]
            return not matched, {"field": field, "matched_patterns": matched}, f"{field} contains no forbidden text."

        return forbidden_text

    if rule_type == "conditional_required":
        condition_field = str(definition.get("condition_field", ""))
        condition_value = definition.get("condition_value")

        def conditional_required(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            actual = get(record, condition_field)
            required = actual == condition_value
            present = exists(get(record, field))
            ok = present if required else True
            return ok, {
                "condition_field": condition_field,
                "condition_value": condition_value,
                "actual_condition": actual,
                "field": field,
                "present": present,
            }, f"{field} is present when required."

        return conditional_required

    if rule_type == "cross_field_lte":
        right_field = str(definition.get("right_field", ""))

        def cross_field_lte(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            left = get(record, field)
            right = get(record, right_field)
            ok = isinstance(left, (int, float)) and isinstance(right, (int, float)) and float(left) <= float(right)
            return ok, {"left_field": field, "left": left, "right_field": right_field, "right": right}, f"{field} does not exceed {right_field}."

        return cross_field_lte

    if rule_type == "date_order":
        end_field = str(definition.get("end_field", ""))

        def date_order(record: NormalizedRecord) -> tuple[bool, dict[str, Any], str]:
            start_raw = get(record, field)
            end_raw = get(record, end_field)
            try:
                start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
                ok = start < end
            except Exception:
                ok = False
            return ok, {"start_field": field, "start": start_raw, "end_field": end_field, "end": end_raw}, "Date range is valid."

        return date_order

    raise ValueError(f"Unsupported configurable rule type: {rule_type}")
