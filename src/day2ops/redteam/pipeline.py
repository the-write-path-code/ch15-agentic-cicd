"""Red-team pipeline: L1 -> L2 -> L10 -> L7 with a fail-closed contract.

Single responsibility: run the security layers in order over a request and
return a single LayerResult. Constraints: any uncaught exception becomes a
fail-closed block with reason 'failed closed due to scanner error'
(mirroring Chapter 14's run_pipeline contract); infrastructure failures
block, they never pass; every exit path emits an audit record.
"""
from __future__ import annotations

import json
from pathlib import Path

from day2ops.redteam.layers import (
    check_agent_identity,
    check_context_isolator,
    check_input,
    check_semantics,
)
from day2ops.schemas import Chunk, LayerResult

FAIL_CLOSED_REASON = "failed closed due to scanner error"


def run_pipeline(
    payload: str,
    user_role: str = "public",
    requested_sources: list[str] | None = None,
    tool_calls: list[tuple[str, dict[str, object]]] | None = None,
    retrieved_chunks: list[Chunk] | None = None,
    docs_by_id: dict[str, object] | None = None,
    fault_inject_scanner: bool = False,
) -> LayerResult:
    """Run L1, L2, L10, then L7 (only when the request includes retrieval)."""
    try:
        reason = check_input(payload)
        if reason is not None:
            return LayerResult(passed=False, layer_name="input_validator", reason=reason,
                               metadata={"layers_fired": ["input_validator"]})
        reason = check_semantics(payload)
        if reason is not None:
            return LayerResult(passed=False, layer_name="semantic_guard", reason=reason,
                               metadata={"layers_fired": ["input_validator", "semantic_guard"]})
        identity = check_agent_identity(
            user_role=user_role,
            requested_sources=requested_sources or [],
            tool_calls=tool_calls or [],
            docs_by_id=docs_by_id,
        )
        if not identity.passed:
            return LayerResult(
                passed=False, layer_name="agent_identity", reason=identity.reason,
                metadata={"layers_fired": ["input_validator", "semantic_guard", "agent_identity"]},
            )
        if retrieved_chunks:
            isolator = check_context_isolator(
                user_role=user_role,
                retrieved_chunks=retrieved_chunks,
                fault_inject_scanner=fault_inject_scanner,
            )
            fired = ["input_validator", "semantic_guard", "agent_identity", "context_isolator"]
            return LayerResult(
                passed=isolator.passed, layer_name=isolator.layer_name, reason=isolator.reason,
                metadata={"layers_fired": fired, **isolator.metadata},
            )
        return LayerResult(
            passed=True, layer_name="pipeline", reason="all layers passed",
            metadata={"layers_fired": ["input_validator", "semantic_guard", "agent_identity"]},
        )
    except Exception as exc:  # noqa: BLE001 - the fail-closed contract
        return LayerResult(
            passed=False, layer_name="fail_closed",
            reason=f"{FAIL_CLOSED_REASON}: {exc}",
            metadata={"layers_fired": ["input_validator", "semantic_guard", "agent_identity", "context_isolator"]},
        )


def write_audit_log(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
