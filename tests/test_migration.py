"""Behavior tests for the model migration gate (Chapter 15.2)."""
from __future__ import annotations

import os
import subprocess
import sys

from day2ops.config import REPO_ROOT
from day2ops.migration.signature_compat import diff_schemas
from day2ops.migration.token_report import build_token_report
from day2ops.schemas import RetrievedChunk, TokenUsage, TraceRecord


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    src = str(REPO_ROOT / "src")
    if src not in parts:
        parts.append(src)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def test_candidate_v1_passes_migration_gate() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/swap_model.py"), "--candidate", "traces_candidate_v1"],
        capture_output=True, text=True, timeout=300, env=_script_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MIGRATION GATE: PASS" in result.stdout


def test_regressed_candidate_fails_migration_gate() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/swap_model.py"), "--candidate", "traces_candidate_regressed"],
        capture_output=True, text=True, timeout=300, env=_script_env(),
    )
    assert result.returncode != 0
    assert "high-risk faithfulness" in result.stderr
    assert "PRODUCTION-FROZEN decision changed" in result.stderr


def test_removed_parameter_is_a_breaking_change() -> None:
    old = {"properties": {"query": {"type": "string"}, "department": {"type": "string"}}, "required": ["query"]}
    new = {"properties": {"query": {"type": "string"}, "policy_search": {"type": "string"}}, "required": ["query"]}
    diff = diff_schemas("lookup_policy", old, new)
    assert diff.breaking
    assert "department" in diff.removed_params
    assert "policy_search" in diff.added_params


def test_newly_required_parameter_is_a_breaking_change() -> None:
    old = {"properties": {"query": {"type": "string"}}, "required": ["query"]}
    new = {"properties": {"query": {"type": "string"}, "scope": {"type": "string"}}, "required": ["query", "scope"]}
    diff = diff_schemas("lookup_policy", old, new)
    assert diff.breaking
    assert "scope" in diff.added_params


def test_added_optional_parameter_is_not_breaking() -> None:
    old = {"properties": {"query": {"type": "string"}}, "required": ["query"]}
    new = {"properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}
    diff = diff_schemas("lookup_policy", old, new)
    assert not diff.breaking


def test_token_report_flags_budget_overflow() -> None:
    traces = [
        TraceRecord(
            case_id=f"c{i}", question="q", prompt_version="v", persona="faithful",
            retrieved=[RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)],
            answer="a", citations=[], sufficiency="SUFFICIENT",
            gate_decision="ANSWER", risk_tier="low", status="PROVISIONAL",
            token_usage=TokenUsage(prompt_tokens=200000, completion_tokens=10),
        )
        for i in range(5)
    ]
    report = build_token_report(traces, tokens_per_minute=100000)
    assert report.warnings
    assert report.per_case_max > 100000


def test_token_report_passes_within_budget() -> None:
    traces = [
        TraceRecord(
            case_id=f"c{i}", question="q", prompt_version="v", persona="faithful",
            retrieved=[RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)],
            answer="a", citations=[], sufficiency="SUFFICIENT",
            gate_decision="ANSWER", risk_tier="low", status="PROVISIONAL",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=20),
        )
        for i in range(5)
    ]
    report = build_token_report(traces, tokens_per_minute=100000)
    assert report.warnings == []
    assert report.total_tokens == 5 * 120
    assert report.per_case_p95 == 120
