"""Tool signature validation and old-vs-new schema diffing (Chapter 15.2).

Single responsibility: check recorded tool calls from candidate traces against
the committed JSON Schemas, and diff two schema versions for the same tool,
flagging added, removed, and changed parameters with a breaking-change
verdict. Constraints: pure functions over committed schemas; no network.
"""
from __future__ import annotations

import json
from pathlib import Path

from day2ops.config import REPO_ROOT
from day2ops.schemas import SignatureDiff, ToolCall, TraceRecord


def load_schemas(directory: Path | None = None) -> dict[str, dict[str, object]]:
    base = directory or (REPO_ROOT / "data" / "tools" / "tool_schemas")
    schemas: dict[str, dict[str, object]] = {}
    if not base.exists():
        return schemas
    for path in sorted(base.glob("*.json")):
        schemas[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return schemas


def _validate_one(tool: str, arguments: dict[str, object], schema: dict[str, object]) -> str | None:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    required = schema.get("required", [])
    if not isinstance(required, list):
        required = []
    for param in required:
        if isinstance(param, str) and param not in arguments:
            return f"missing required parameter '{param}'"
    for name, value in arguments.items():
        spec = properties.get(name)
        if not isinstance(spec, dict):
            return f"unknown parameter '{name}'"
        spec_type = spec.get("type")
        if spec_type == "string" and not isinstance(value, str):
            return f"parameter '{name}' must be a string"
        if spec_type == "number" and not isinstance(value, (int, float)):
            return f"parameter '{name}' must be a number"
        if spec_type == "integer" and not isinstance(value, int):
            return f"parameter '{name}' must be an integer"
        enum_values = spec.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            return f"parameter '{name}' value not in enum {enum_values}"
    return None


def validate_recorded_calls(
    traces: list[TraceRecord], schemas: dict[str, dict[str, object]]
) -> list[SignatureDiff]:
    diffs: list[SignatureDiff] = []
    for trace in traces:
        call: ToolCall
        for call in trace.tool_calls:
            schema = schemas.get(call.tool)
            if schema is None:
                diffs.append(SignatureDiff(
                    tool=call.tool, added_params=[], removed_params=[], changed_params=[],
                    breaking=True,
                    details=f"{trace.case_id}: tool '{call.tool}' has no committed schema",
                ))
                continue
            problem = _validate_one(call.tool, call.arguments, schema)
            if problem is not None:
                diffs.append(SignatureDiff(
                    tool=call.tool, added_params=[], removed_params=[], changed_params=[],
                    breaking=True,
                    details=f"{trace.case_id}: {problem}",
                ))
    return diffs


def _required_set(schema: dict[str, object]) -> set[str]:
    raw = schema.get("required", [])
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def diff_schemas(
    tool: str, old_schema: dict[str, object], new_schema: dict[str, object]
) -> SignatureDiff:
    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    if not isinstance(old_props, dict):
        old_props = {}
    if not isinstance(new_props, dict):
        new_props = {}
    old_names = set(old_props)
    new_names = set(new_props)
    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)
    changed: list[str] = []
    for name in sorted(old_names & new_names):
        old_type = old_props[name].get("type") if isinstance(old_props[name], dict) else None
        new_type = new_props[name].get("type") if isinstance(new_props[name], dict) else None
        if old_type != new_type:
            changed.append(name)
    old_required = _required_set(old_schema)
    new_required = _required_set(new_schema)
    breaking = bool(removed or changed or (new_required - old_required))
    details = (
        f"added={added or 'none'}, removed={removed or 'none'}, changed={changed or 'none'}, "
        f"newly required={sorted(new_required - old_required) or 'none'}"
    )
    return SignatureDiff(
        tool=tool, added_params=added, removed_params=removed,
        changed_params=changed, breaking=breaking, details=details,
    )
