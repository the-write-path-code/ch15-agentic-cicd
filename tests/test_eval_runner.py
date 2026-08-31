"""Behavior tests for the mock-mode evaluation pipeline and merge gates."""
from __future__ import annotations

import os
import subprocess
import sys

from day2ops.config import REPO_ROOT, load_thresholds
from day2ops.eval import runner
from day2ops.schemas import GateDecision, GoldenCase

PROMPTS = REPO_ROOT / "data/prompts"
THRESHOLDS = load_thresholds()
PROFILE = THRESHOLDS.profiles[THRESHOLDS.active_profile]


def _golden() -> list[GoldenCase]:
    return [
        GoldenCase.model_validate_json(line)
        for line in (REPO_ROOT / "data/golden/golden_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_run(corpus, prompt: str):
    return runner.run_mock(_golden(), corpus, PROMPTS / prompt, PROFILE)


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    src = str(REPO_ROOT / "src")
    if src not in parts:
        parts.append(src)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def test_mock_run_passes_merge_gates(corpus) -> None:
    run = _mock_run(corpus, "answer_v1.txt")
    violations = runner.evaluate_ci_gates(run, _golden(), THRESHOLDS.ci_gates)
    assert violations == []
    assert run.case_count == 60
    assert run.corpus_quarantined == ["HR-2026-10#3"]


def test_miss_cases_abstain_and_clean_cases_answer(corpus) -> None:
    run = _mock_run(corpus, "answer_v1.txt")
    cases = {c.case_id: c for c in _golden()}
    by_tag: dict[str, set[str]] = {}
    for r in run.results:
        by_tag.setdefault(cases[r.case_id].failure_mode_tag, set()).add(r.decision.value)
    assert by_tag["retrieval-miss"] == {"ABSTAIN"}
    assert "ANSWER" in by_tag["none"]
    assert by_tag["conflicting-evidence"] == {"QUALIFIED_ANSWER", "HUMAN_REVIEW"}


def test_broken_prompt_fails_the_gate_deterministically(corpus) -> None:
    run = _mock_run(corpus, "answer_v1_broken.txt")
    violations = runner.evaluate_ci_gates(run, _golden(), THRESHOLDS.ci_gates)
    assert violations != []
    assert any("faithfulness" in v for v in violations)
    assert any("unsupported claim" in v for v in violations)


def test_restricted_documents_are_filtered_before_scoring(corpus) -> None:
    run = _mock_run(corpus, "answer_v1.txt")
    for r in run.results:
        retrieved_docs = [rc.chunk_id.split("#")[0] for rc in r.retrieved]
        assert "SEC-2026-02" not in retrieved_docs


def test_frozen_decision_change_is_merge_blocking(corpus) -> None:
    run = _mock_run(corpus, "answer_v1.txt")
    baseline = runner.load_baseline(REPO_ROOT / "baselines/metrics_baseline.json")
    flipped = run.model_copy(deep=True)
    for r in flipped.results:
        if r.case_id == "golden-0001":
            r.decision = GateDecision.ABSTAIN
    violations = runner.evaluate_ci_gates(flipped, _golden(), THRESHOLDS.ci_gates, baseline)
    assert any("golden-0001" in v and "PRODUCTION-FROZEN" in v for v in violations)
    clean = runner.evaluate_ci_gates(run, _golden(), THRESHOLDS.ci_gates, baseline)
    assert not any("golden-0001" in v for v in clean)


def test_replay_of_committed_traces_matches_baseline(corpus) -> None:
    traces = runner.load_traces(REPO_ROOT / "data/traces/baseline/traces_v1.jsonl")
    run = runner.run_replay(_golden(), corpus, traces, PROFILE)
    assert run.case_count == 60
    assert run.replay_mismatches == []


def test_run_eval_script_mock_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/run_eval.py"), "--mode", "mock", "--baseline", "none"],
        capture_output=True, text=True, timeout=300, env=_script_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (REPO_ROOT / "reports/eval_report.json").exists()
    assert (REPO_ROOT / "reports/eval_summary.md").exists()


def test_run_eval_script_broken_prompt_exits_nonzero() -> None:
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts/run_eval.py"), "--mode", "mock",
            "--prompt", str(REPO_ROOT / "data/prompts/answer_v1_broken.txt"), "--baseline", "none",
        ],
        capture_output=True, text=True, timeout=300, env=_script_env(),
    )
    assert result.returncode != 0
    assert "MERGE GATE: FAIL" in result.stderr
