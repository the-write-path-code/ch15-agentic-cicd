"""HITL case promotion (Chapter 15.5): a one-way ratchet.

Single responsibility: flip a PROVISIONAL golden case to PRODUCTION-FROZEN and
append an audit entry recording who promoted it and on what evidence. The
ratchet only turns one way; demotion attempts are refused with a clear error.
Constraints: never rewrites existing case content, only the status field.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from day2ops.schemas import AuditEntry, CaseStatus, GoldenCase


def promote_case(
    case_id: str,
    reviewer: str,
    evidence: str,
    golden_path: Path,
    audit_log_path: Path,
) -> GoldenCase:
    lines = [
        line for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    cases = [GoldenCase.model_validate_json(line) for line in lines]
    target = next((c for c in cases if c.case_id == case_id), None)
    if target is None:
        raise ValueError(f"case not found: {case_id}")
    if target.status == CaseStatus.PRODUCTION_FROZEN:
        raise ValueError(f"{case_id} is already PRODUCTION-FROZEN")
    promoted = target.model_copy(update={"status": CaseStatus.PRODUCTION_FROZEN})
    rewritten = [promoted if c.case_id == case_id else c for c in cases]
    golden_path.write_text(
        "\n".join(c.model_dump_json() for c in rewritten) + "\n", encoding="utf-8"
    )
    entry = AuditEntry(
        case_id=case_id,
        from_status=target.status.value,
        to_status=CaseStatus.PRODUCTION_FROZEN.value,
        reviewer=reviewer,
        evidence=evidence,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry.model_dump_json() + "\n")
    return promoted


def demote_case(case_id: str, golden_path: Path) -> None:
    """Deliberately unsupported: promotion is a one-way ratchet."""
    lines = [
        line for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    cases = [GoldenCase.model_validate_json(line) for line in lines]
    target = next((c for c in cases if c.case_id == case_id), None)
    if target is not None and target.status == CaseStatus.PRODUCTION_FROZEN:
        raise ValueError(
            f"{case_id}: promotion is a one-way ratchet; demotion from "
            f"PRODUCTION-FROZEN is refused"
        )
    raise ValueError(f"case not found or not frozen: {case_id}")
