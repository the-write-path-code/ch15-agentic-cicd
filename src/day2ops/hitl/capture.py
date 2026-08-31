"""HITL override capture (Chapter 15.5).

Single responsibility: validate reviewer override records and convert every
`assert` disposition into a new PROVISIONAL golden case with origin `hitl`.
Security blocks additionally generate an adversarial twin case, so the
red-team suite grows from real incidents. Constraints: never touches existing
cases; refuses duplicate case ids; refuses to reuse retired ids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from day2ops.schemas import CaseStatus, GoldenCase, OverrideRecord

VALID_DISPOSITIONS = {"assert", "ignore", "escalate"}

ModelT = TypeVar("ModelT", bound=BaseModel)


def _next_case_id(existing_ids: set[str], retired_ids: set[str]) -> str:
    used = existing_ids | retired_ids
    n = 1
    while f"golden-{n:04d}" in used:
        n += 1
    return f"golden-{n:04d}"


def _load_jsonl(path: Path, model: type[ModelT]) -> list[ModelT]:
    records: list[ModelT] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(model.model_validate_json(line))
    return records


def capture_overrides(
    overrides_path: Path,
    golden_path: Path,
    retired_ids_path: Path,
    adversarial_path: Path | None = None,
) -> dict[str, object]:
    overrides = _load_jsonl(overrides_path, OverrideRecord)
    golden = _load_jsonl(golden_path, GoldenCase)
    existing = {c.case_id for c in golden}
    existing_questions = {c.question for c in golden}
    retired_raw = json.loads(retired_ids_path.read_text(encoding="utf-8")) if retired_ids_path.exists() else {"retired_ids": []}
    retired = set(retired_raw.get("retired_ids", []))

    new_cases: list[GoldenCase] = []
    twins: list[dict[str, object]] = []
    skipped: list[str] = []
    rejected: list[str] = []

    for record in overrides:
        if record.disposition not in VALID_DISPOSITIONS:
            rejected.append(f"{record.override_id}: unknown disposition '{record.disposition}'")
            continue
        if record.question in existing_questions:
            skipped.append(f"{record.override_id}: question already covered by an existing case")
            continue
        if record.disposition != "assert":
            skipped.append(f"{record.override_id}: disposition '{record.disposition}' records no case")
            continue
        case_id = _next_case_id(existing, retired)
        new_case = GoldenCase(
            case_id=case_id,
            question=record.question,
            risk_tier=record.risk_tier,
            expected_answer=record.corrected_output,
            expected_doc_ids=record.expected_doc_ids,
            should_answer=True,
            failure_mode_tag="hitl-assert" if not record.security_block else "hitl-security",
            status=CaseStatus.PROVISIONAL,
            origin="hitl",
            added_at=record.timestamp.split("T")[0],
            added_by=record.reviewer,
        )
        new_cases.append(new_case)
        existing.add(case_id)
        existing_questions.add(record.question)
        if record.security_block:
            twins.append({
                "case_id": f"adv-hitl-{case_id}",
                "category": "hitl_security_block",
                "payload": record.question,
                "delivery": "user_message",
                "expected_blocked_layer": record.blocked_layer or 10,
                "expected_reason_pattern": "agent identity",
                "must_fail_closed": False,
                "control_case_id": None,
                "control_case": False,
                "user_role": "public",
                "requested_sources": [],
                "retrieved_chunk_ids": [],
                "tool_calls": [],
            })

    if new_cases:
        with golden_path.open("a", encoding="utf-8") as handle:
            for case in new_cases:
                handle.write(case.model_dump_json() + "\n")
    if twins and adversarial_path is not None:
        with adversarial_path.open("a", encoding="utf-8") as handle:
            for twin in twins:
                handle.write(json.dumps(twin) + "\n")

    return {
        "overrides_read": len(overrides),
        "cases_added": len(new_cases),
        "twins_added": len(twins),
        "skipped": skipped,
        "rejected": rejected,
        "new_case_ids": [c.case_id for c in new_cases],
    }
