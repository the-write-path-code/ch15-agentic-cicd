#!/usr/bin/env python3
"""Chapter 15.1: run the continuous grounding validation gate.

Modes: --mode mock (default, deterministic, offline), --mode replay (cached
traces through the scoring stack), --mode live (real inference, live extra).
Writes reports/eval_report.json and reports/eval_summary.md, exits nonzero on
merge-gate violations. --update-baseline rewrites baselines/metrics_baseline.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT, golden_path, load_thresholds  # noqa: E402
from day2ops.corpus.loader import load_corpus  # noqa: E402
from day2ops.eval import runner  # noqa: E402
from day2ops.eval.ragas_ci import ragas_judge_available  # noqa: E402
from day2ops.reporting.render import report_json, summary_markdown  # noqa: E402
from day2ops.schemas import GoldenCase  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "replay", "live"], default="mock")
    parser.add_argument(
        "--prompt", default=None,
        help="answer prompt file (default data/prompts/answer_v1.txt)",
    )
    parser.add_argument("--traces", default=None, help="trace file for replay mode")
    parser.add_argument(
        "--baseline", default="baselines/metrics_baseline.json",
        help="baseline file to compare against (use 'none' to skip)",
    )
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--fail-on", default="regression", choices=["regression", "never"])
    parser.add_argument("--ragas", action="store_true", help="enable the real Ragas judge")
    args = parser.parse_args()

    thresholds = load_thresholds()
    profile = thresholds.profiles[thresholds.active_profile]
    corpus = load_corpus()
    golden = [
        GoldenCase.model_validate_json(line)
        for line in golden_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    prompt_path = Path(args.prompt) if args.prompt else REPO_ROOT / "data/prompts/answer_v1.txt"

    if args.mode == "mock":
        run = runner.run_mock(golden, corpus, prompt_path, profile)
    elif args.mode == "replay":
        if args.traces is None:
            print("replay mode requires --traces", file=sys.stderr)
            return 2
        run = runner.run_replay(golden, corpus, runner.load_traces(Path(args.traces)), profile)
    else:
        print("live mode requires the `live` extra: uv sync --extra live", file=sys.stderr)
        return 2

    if args.ragas and not ragas_judge_available():
        print("the ragas extra is not installed: uv sync --extra ragas", file=sys.stderr)
        return 2

    baseline = None
    baseline_path = None
    if args.baseline != "none":
        baseline_path = REPO_ROOT / args.baseline
        if baseline_path.exists():
            baseline = runner.load_baseline(baseline_path)

    violations = runner.evaluate_ci_gates(run, golden, thresholds.ci_gates, baseline)

    if args.update_baseline:
        runner.write_baseline(
            run, baseline_path or (REPO_ROOT / "baselines/metrics_baseline.json"),
            "2026-08-30T00:00:00Z",
        )
        print(f"baseline written to {baseline_path or 'baselines/metrics_baseline.json'}")

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "eval_report.json").write_text(
        json.dumps(report_json(run, violations), indent=2) + "\n", encoding="utf-8"
    )
    summary = summary_markdown(run, violations, baseline)
    (reports_dir / "eval_summary.md").write_text(summary, encoding="utf-8")
    print(summary)

    if violations:
        print(f"\nMERGE GATE: FAIL ({len(violations)} violation(s))", file=sys.stderr)
        return 1
    print("\nMERGE GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
