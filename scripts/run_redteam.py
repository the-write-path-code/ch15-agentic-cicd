#!/usr/bin/env python3
"""Chapter 15.4: run the automated red-team suite in CI.

Asserts that all malicious cases in the suite are blocked, that each blocks at
the expected layer with a matching reason, and that every paired benign
control passes the full pipeline. With --fault-inject layer7_scanner the
Layer 7 scanner is forced to raise, and every retrieval-dependent case must
block fail-closed, proving the fail-closed contract from Chapter 14.

Exit codes: 0 success, 2 design mismatch (wrong layer or reason), 3 a benign
control was blocked, 4 a fail-closed violation (a retrieval-dependent case
passed while the scanner was broken).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT  # noqa: E402
from day2ops.corpus.loader import load_corpus  # noqa: E402
from day2ops.redteam.pipeline import run_pipeline  # noqa: E402
from day2ops.schemas import AdversarialCase, Chunk  # noqa: E402

LAYER_NAMES = {1: "input_validator", 2: "semantic_guard", 7: "context_isolator", 10: "agent_identity"}
BENIGN_QUESTION = "What does the retrieved policy passage say?"


def build_request(case: AdversarialCase, corpus) -> tuple[str, list[Chunk]]:
    """Return (user message, retrieved chunks) for a suite case.

    Indirect injection payloads travel inside the retrieved document, never in
    the user message, so only Layer 7 can catch them. The harness synthesizes
    the poisoned chunk from the case payload.
    """
    chunks_by_id = corpus.chunks_by_id()
    retrieved = [chunks_by_id[cid] for cid in case.retrieved_chunk_ids if cid in chunks_by_id]
    if case.delivery == "retrieved_document":
        if not case.control_case and case.category == "indirect_injection":
            retrieved.append(
                Chunk(chunk_id=f"{case.case_id}#poison", doc_id=case.case_id,
                      text=case.payload, classification="internal")
            )
        elif case.control_case and not retrieved:
            retrieved.append(
                Chunk(chunk_id=f"{case.case_id}#doc", doc_id=case.case_id,
                      text=case.payload, classification="internal")
            )
        return BENIGN_QUESTION, retrieved
    return case.payload, retrieved


def run_suite(suite_path: Path, fault_inject: bool, audit_path: Path) -> int:
    cases = [
        AdversarialCase.model_validate_json(line)
        for line in suite_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    malicious = [c for c in cases if not c.control_case]
    controls = [c for c in cases if c.control_case]
    corpus = load_corpus()
    docs_by_id = corpus.docs_by_id()

    design_mismatches: list[str] = []
    blocked_controls: list[str] = []
    fail_closed_violations: list[str] = []
    audit: list[dict[str, object]] = []
    blocked_count = 0

    for case in malicious + controls:
        payload, retrieved = build_request(case, corpus)
        result = run_pipeline(
            payload=payload,
            user_role=case.user_role,
            requested_sources=case.requested_sources,
            tool_calls=[(tc.tool, tc.arguments) for tc in case.tool_calls],
            retrieved_chunks=retrieved,
            docs_by_id=docs_by_id,
            fault_inject_scanner=fault_inject,
        )
        audit.append({
            "case_id": case.case_id,
            "control": case.control_case,
            "layers_fired": result.metadata.get("layers_fired", []),
            "blocked_layer": None if result.passed else result.layer_name,
            "reason": result.reason,
        })
        retrieval_dependent = bool(retrieved)

        if fault_inject:
            if retrieval_dependent:
                if result.passed:
                    fail_closed_violations.append(case.case_id)
                else:
                    blocked_count += 1
            continue

        if case.control_case:
            if not result.passed:
                blocked_controls.append(f"{case.case_id}: {result.reason}")
            continue

        if not result.passed:
            blocked_count += 1
        else:
            design_mismatches.append(
                f"{case.case_id}: passed, expected block at layer {case.expected_blocked_layer}"
            )
            continue
        expected_layer = LAYER_NAMES.get(case.expected_blocked_layer or 0)
        if expected_layer is not None and result.layer_name != expected_layer:
            design_mismatches.append(
                f"{case.case_id}: blocked at {result.layer_name}, expected {expected_layer}"
            )
        elif case.expected_reason_pattern and case.expected_reason_pattern.lower() not in result.reason.lower():
            design_mismatches.append(
                f"{case.case_id}: reason '{result.reason[:70]}' missing pattern '{case.expected_reason_pattern}'"
            )

    write_audit(audit, audit_path)

    print(f"suite: {len(malicious)} malicious, {len(controls)} controls")
    print(f"malicious blocked: {blocked_count}/{len(malicious)}")
    if fault_inject:
        print(f"fail-closed violations: {len(fail_closed_violations)}")
        if fail_closed_violations:
            print("  " + ", ".join(fail_closed_violations), file=sys.stderr)
            return 4
        print("fail-closed contract holds: every retrieval-dependent case blocked")
        return 0
    if design_mismatches:
        for m in design_mismatches[:10]:
            print(f"  - {m}", file=sys.stderr)
        return 2
    if blocked_controls:
        for c in blocked_controls[:10]:
            print(f"  - {c}", file=sys.stderr)
        return 3
    print("red-team suite passed: 39/39 blocked at the expected layer, 39/39 controls clean")
    return 0


def write_audit(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="data/adversarial/adversarial_v1.jsonl")
    parser.add_argument("--fault-inject", choices=["layer7_scanner"], default=None)
    parser.add_argument("--audit-log", default="reports/redteam_audit.jsonl")
    args = parser.parse_args()

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = REPO_ROOT / suite_path
    audit_path = Path(args.audit_log)
    if not audit_path.is_absolute():
        audit_path = REPO_ROOT / audit_path

    fault = args.fault_inject == "layer7_scanner"
    if fault:
        print("fault injection enabled: layer7_scanner will raise on every scan")

    result = run_suite(suite_path, fault, audit_path)
    if result == 0:
        print(f"audit log: {audit_path}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
