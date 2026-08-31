#!/usr/bin/env python3
"""Chapter 15.5 (mirrors 4.5): calibrate threshold profiles over the golden set.

Re-runs the three threshold profiles over the full golden dataset, prints the
decision matrix with false-pass and false-block counts by risk tier, and
refuses to mark any profile PRODUCTION-FROZEN unless human review audit data
exists in data/golden/audit_log.jsonl. Threshold profiles stay PROVISIONAL
until that evidence lands.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from day2ops.config import REPO_ROOT, golden_path, load_thresholds  # noqa: E402
from day2ops.corpus.loader import load_corpus  # noqa: E402
from day2ops.eval import runner  # noqa: E402
from day2ops.schemas import GateDecision, GoldenCase  # noqa: E402

MIN_AUDIT_ENTRIES = 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", default=None,
                        help="profile name to mark PRODUCTION-FROZEN after calibration")
    args = parser.parse_args()

    thresholds = load_thresholds()
    corpus = load_corpus()
    golden = [
        GoldenCase.model_validate_json(line)
        for line in golden_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = {c.case_id: c for c in golden}

    prompt_path = REPO_ROOT / "data/prompts/answer_v1.txt"
    for name, profile in thresholds.profiles.items():
        run = runner.run_mock(golden, corpus, prompt_path, profile)
        decisions: dict[str, Counter[str]] = {tier: Counter() for tier in ("low", "medium", "high")}
        false_pass: Counter[str] = Counter()
        false_block: Counter[str] = Counter()
        for r in run.results:
            case = cases[r.case_id]
            tier = r.risk_tier.value
            decisions[tier][r.decision.value] += 1
            answered = r.decision in (GateDecision.ANSWER, GateDecision.QUALIFIED_ANSWER)
            if not case.should_answer and answered:
                false_pass[tier] += 1
            if case.should_answer and r.decision in (GateDecision.ABSTAIN, GateDecision.BLOCK):
                false_block[tier] += 1
        print(f"profile {name} ({profile.status}):")
        for tier in ("low", "medium", "high"):
            print(f"  {tier:6s} decisions={dict(decisions[tier])} "
                  f"false_pass={false_pass[tier]} false_block={false_block[tier]}")
        overall = Counter(r.decision.value for r in run.results)
        print(f"  overall decisions={dict(overall)}")
        print()

    if args.freeze is None:
        print("no --freeze given; leaving profile statuses unchanged")
        return 0

    audit_log = REPO_ROOT / "data/golden/audit_log.jsonl"
    entries = [
        line for line in audit_log.read_text(encoding="utf-8").splitlines() if line.strip()
    ] if audit_log.exists() else []
    if len(entries) < MIN_AUDIT_ENTRIES:
        print(
            f"REFUSED: cannot freeze '{args.freeze}' without human review audit data "
            f"(need at least {MIN_AUDIT_ENTRIES} audit entry, found {len(entries)}). "
            "Promote HITL cases first; see scripts/promote_cases.py.",
            file=sys.stderr,
        )
        return 2

    if args.freeze not in thresholds.profiles:
        print(f"REFUSED: unknown profile '{args.freeze}'", file=sys.stderr)
        return 2

    thresholds_path = REPO_ROOT / "data/config/thresholds.yaml"
    raw = yaml.safe_load(thresholds_path.read_text(encoding="utf-8"))
    raw["profiles"][args.freeze]["status"] = "PRODUCTION-FROZEN"
    thresholds_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    print(f"profile '{args.freeze}' marked PRODUCTION-FROZEN in {thresholds_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
