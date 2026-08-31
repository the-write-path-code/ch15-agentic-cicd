#!/usr/bin/env python3
"""Chapter 15.2: replay a candidate model's traces as a migration gate.

Replays the candidate's cached traces against the golden set, compares
per-metric aggregates to the committed baseline within tolerance bands,
validates recorded tool-calling signatures against the committed JSON
Schemas, and produces reports/migration_report.md. Exits nonzero when
high-risk faithfulness drops below the gate or any PRODUCTION-FROZEN case
regresses. The Gemini example this mirrors is a next model release, never an
upgrade from Gemini 1.5 Flash; the book's baseline is already Gemini 2.5 Flash.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT, golden_path, load_models, load_thresholds  # noqa: E402
from day2ops.corpus.loader import load_corpus  # noqa: E402
from day2ops.eval import runner  # noqa: E402
from day2ops.migration.signature_compat import load_schemas, validate_recorded_calls  # noqa: E402
from day2ops.migration.token_report import build_token_report  # noqa: E402
from day2ops.schemas import CaseStatus, GoldenCase  # noqa: E402

TOLERANCE_METRICS = (
    "faithfulness", "answer_relevance", "claim_grounding",
    "context_precision", "context_recall", "recall_at_5",
)


def resolve_candidate(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct
    fixture = REPO_ROOT / "data/traces/candidate_fixture" / f"{name}.jsonl"
    if fixture.exists():
        return fixture
    fixture = REPO_ROOT / "data/traces/candidate_fixture" / name
    if fixture.exists():
        return fixture
    raise SystemExit(f"candidate trace file not found: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True,
                        help="candidate trace file or fixture name, e.g. traces_candidate_v1")
    parser.add_argument("--baseline", default="baselines/metrics_baseline.json")
    parser.add_argument("--report", default="reports/migration_report.md")
    args = parser.parse_args()

    candidate_path = resolve_candidate(args.candidate)
    thresholds = load_thresholds()
    profile = thresholds.profiles[thresholds.active_profile]
    models = load_models()
    corpus = load_corpus()
    golden = [
        GoldenCase.model_validate_json(line)
        for line in golden_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    traces = runner.load_traces(candidate_path)
    baseline = runner.load_baseline(REPO_ROOT / args.baseline)

    replay = runner.run_replay(golden, corpus, traces, profile)
    if replay.case_count == 0:
        print("candidate traces contain no golden cases", file=sys.stderr)
        return 1

    violations: list[str] = []
    deltas: dict[str, float] = {}
    for metric in TOLERANCE_METRICS:
        delta = replay.overall[metric] - baseline.overall[metric]
        deltas[metric] = delta
        tolerance = getattr(thresholds.migration_tolerances, metric)
        if abs(delta) > tolerance:
            violations.append(
                f"{metric} delta {delta:+.3f} exceeds tolerance {tolerance}"
            )

    high_faithfulness = replay.aggregates["high"]["faithfulness"]
    if high_faithfulness < thresholds.ci_gates.faithfulness_min_high_risk:
        violations.append(
            f"high-risk faithfulness {high_faithfulness:.3f} below "
            f"{thresholds.ci_gates.faithfulness_min_high_risk}"
        )

    for case in golden:
        if case.status != CaseStatus.PRODUCTION_FROZEN:
            continue
        current = next((r for r in replay.results if r.case_id == case.case_id), None)
        base = baseline.per_case.get(case.case_id)
        if current is None or base is None:
            continue
        if base.decision != current.decision:
            violations.append(
                f"{case.case_id}: PRODUCTION-FROZEN decision changed from "
                f"{base.decision.value} to {current.decision.value}"
            )

    schemas = load_schemas()
    signature_diffs = validate_recorded_calls(traces, schemas)
    for diff in signature_diffs:
        if diff.breaking:
            violations.append(f"tool signature violation: {diff.details}")

    token_report = build_token_report(traces, models.generator.rate_limits.tokens_per_minute)
    for warning in token_report.warnings:
        violations.append(f"token budget: {warning}")

    report_dir = (REPO_ROOT / args.report).parent
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Model migration report",
        "",
        f"- Candidate: `{candidate_path.name}`",
        f"- Prompt version: `{replay.prompt_version}`",
        f"- Cases replayed: {replay.case_count}",
        f"- Baseline: `{args.baseline}` (prompt `{baseline.prompt_version}`)",
        "",
        "## Metrics vs baseline",
        "",
        "| Metric | Baseline | Candidate | Delta | Tolerance | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for metric in TOLERANCE_METRICS:
        tolerance = getattr(thresholds.migration_tolerances, metric)
        verdict = "OK" if abs(deltas[metric]) <= tolerance else "OUT"
        lines.append(
            f"| {metric} | {baseline.overall[metric]:.3f} | {replay.overall[metric]:.3f} "
            f"| {deltas[metric]:+.3f} | {tolerance} | {verdict} |"
        )
    lines += [
        "",
        f"High-risk faithfulness: {high_faithfulness:.3f} "
        f"(gate: {thresholds.ci_gates.faithfulness_min_high_risk})",
        "",
        "## Tool signature validation",
        "",
    ]
    if signature_diffs:
        for diff in signature_diffs:
            lines.append(f"- `{diff.tool}`: {diff.details}")
    else:
        lines.append("- No recorded tool calls violate the committed schemas.")
    lines += [
        "",
        "## Token usage",
        "",
        f"- Cases: {token_report.case_count}",
        f"- Prompt tokens: {token_report.prompt_tokens}",
        f"- Completion tokens: {token_report.completion_tokens}",
        f"- Total tokens: {token_report.total_tokens}",
        f"- Per-case p95: {token_report.per_case_p95}",
        f"- Per-case max: {token_report.per_case_max}",
        f"- Generator budget: {models.generator.rate_limits.tokens_per_minute} tokens/min",
    ]
    if token_report.warnings:
        lines += ["", "Warnings:"]
        lines += [f"- {warning}" for warning in token_report.warnings]
    lines += ["", "## Verdict", ""]
    if violations:
        lines.append("**BLOCKED** — do not promote this model. Violations:")
        lines += ["", *[f"- {v}" for v in violations]]
    else:
        lines.append("**PASS** — candidate is within tolerance; promote with the usual review.")
    (REPO_ROOT / args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"migration report: {args.report}")
    for metric in TOLERANCE_METRICS:
        print(f"  {metric:18s} delta {deltas[metric]:+.3f}")
    print(f"  high-risk faithfulness {high_faithfulness:.3f}")
    if violations:
        for v in violations:
            print(f"  VIOLATION: {v}", file=sys.stderr)
        print("MIGRATION GATE: FAIL", file=sys.stderr)
        return 1
    print("MIGRATION GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
