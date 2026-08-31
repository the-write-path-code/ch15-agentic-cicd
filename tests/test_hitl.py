"""Behavior tests for the HITL feedback loop (Chapter 15.5)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from day2ops.config import REPO_ROOT
from day2ops.hitl.capture import capture_overrides
from day2ops.hitl.promote import demote_case, promote_case
from day2ops.schemas import CaseStatus, GoldenCase

SEED = REPO_ROOT / "data/hitl/overrides/overrides_seed.jsonl"


def _sandbox(tmp_path: Path) -> tuple[Path, Path, Path]:
    golden = tmp_path / "golden_v1.jsonl"
    retired = tmp_path / "retired_ids.json"
    adversarial = tmp_path / "adversarial_hitl.jsonl"
    shutil.copy(REPO_ROOT / "data/golden/golden_v1.jsonl", golden)
    shutil.copy(REPO_ROOT / "data/golden/retired_ids.json", retired)
    return golden, retired, adversarial


def _script_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    src = str(REPO_ROOT / "src")
    if src not in parts:
        parts.append(src)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def test_assert_overrides_become_provisional_hitl_cases(tmp_path: Path) -> None:
    golden, retired, adversarial = _sandbox(tmp_path)
    result = capture_overrides(SEED, golden, retired, adversarial)
    assert result["cases_added"] == 5
    assert result["twins_added"] == 2
    cases = [
        GoldenCase.model_validate_json(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(cases) == 65
    new = [c for c in cases if c.origin == "hitl"]
    assert len(new) == 5
    assert all(c.status == CaseStatus.PROVISIONAL for c in new)


def test_security_blocks_generate_adversarial_twins(tmp_path: Path) -> None:
    golden, retired, adversarial = _sandbox(tmp_path)
    capture_overrides(SEED, golden, retired, adversarial)
    twins = [
        json.loads(line)
        for line in adversarial.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(twins) == 2
    assert all(t["category"] == "hitl_security_block" for t in twins)


def test_capture_never_touches_existing_cases(tmp_path: Path) -> None:
    golden, retired, adversarial = _sandbox(tmp_path)
    before = [
        GoldenCase.model_validate_json(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    capture_overrides(SEED, golden, retired, adversarial)
    after = [
        GoldenCase.model_validate_json(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    original = {c.case_id: c for c in before}
    for case in after:
        if case.case_id in original:
            assert case == original[case.case_id]


def test_duplicate_capture_is_a_no_op(tmp_path: Path) -> None:
    golden, retired, adversarial = _sandbox(tmp_path)
    first = capture_overrides(SEED, golden, retired, adversarial)
    assert first["cases_added"] == 5
    second = capture_overrides(SEED, golden, retired, adversarial)
    assert second["cases_added"] == 0
    assert second["twins_added"] == 0


def test_promotion_appends_audit_entry_and_refuses_repeats(tmp_path: Path) -> None:
    golden, retired, _ = _sandbox(tmp_path)
    capture_overrides(SEED, golden, retired, None)
    cases = [
        GoldenCase.model_validate_json(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    target = next(c for c in cases if c.origin == "hitl")
    audit = tmp_path / "audit_log.jsonl"

    promoted = promote_case(target.case_id, "m.aggarwal", "ticket-42", golden, audit)
    assert promoted.status == CaseStatus.PRODUCTION_FROZEN
    entries = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) == 1
    assert entries[0]["case_id"] == target.case_id
    assert entries[0]["from_status"] == "PROVISIONAL"
    assert entries[0]["to_status"] == "PRODUCTION-FROZEN"
    assert entries[0]["reviewer"] == "m.aggarwal"
    assert entries[0]["evidence"] == "ticket-42"

    try:
        promote_case(target.case_id, "m.aggarwal", "again", golden, audit)
        raise AssertionError("re-promotion must be refused")
    except ValueError as exc:
        assert "already PRODUCTION-FROZEN" in str(exc)


def test_demotion_is_refused_by_the_ratchet(tmp_path: Path) -> None:
    golden, retired, _ = _sandbox(tmp_path)
    capture_overrides(SEED, golden, retired, None)
    cases = [
        GoldenCase.model_validate_json(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    target = next(c for c in cases if c.origin == "hitl")
    promote_case(target.case_id, "m.aggarwal", "ticket-42", golden, tmp_path / "audit_log.jsonl")
    try:
        demote_case(target.case_id, golden)
        raise AssertionError("demotion must be refused")
    except ValueError as exc:
        assert "one-way ratchet" in str(exc)


def test_capture_script_runs_on_a_copy(tmp_path: Path) -> None:
    committed = REPO_ROOT / "data/golden/golden_v1.jsonl"
    before = committed.read_text(encoding="utf-8")
    golden_copy = tmp_path / "golden_v1.jsonl"
    retired_copy = tmp_path / "retired_ids.json"
    twins = tmp_path / "adversarial_hitl.jsonl"
    shutil.copy(committed, golden_copy)
    shutil.copy(REPO_ROOT / "data/golden/retired_ids.json", retired_copy)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/capture_overrides.py"),
         "--golden", str(golden_copy),
         "--retired", str(retired_copy),
         "--adversarial", str(twins)],
        capture_output=True, text=True, timeout=300, env=_script_env(),
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["cases_added"] == 5
    assert payload["twins_added"] == 2
    cases = [
        GoldenCase.model_validate_json(line)
        for line in golden_copy.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(cases) == 65
    assert sum(1 for line in twins.read_text(encoding="utf-8").splitlines() if line.strip()) == 2

    # the committed golden file is never modified by a test run
    assert committed.read_text(encoding="utf-8") == before
