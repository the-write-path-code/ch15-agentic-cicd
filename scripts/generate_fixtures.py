#!/usr/bin/env python3
"""Regenerate the committed trace fixtures deterministically.

Chapter 15 maintenance utility: rebuilds baselines/metrics_baseline.json,
data/traces/baseline/traces_v1.jsonl, and the two candidate fixtures from the
current corpus, golden dataset, and prompts. Every artifact this script writes
is a pure function of committed inputs, so regeneration is byte-identical.
Run it after changing data/prompts/, data/corpus/, or data/golden/, then review
the diff like any other change.

Usage: uv run python scripts/generate_fixtures.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT, golden_path, load_thresholds  # noqa: E402
from day2ops.corpus.loader import load_corpus  # noqa: E402
from day2ops.eval import runner  # noqa: E402
from day2ops.eval.textutils import is_abstention, split_sentences, strip_citations  # noqa: E402
from day2ops.schemas import GoldenCase, TraceRecord  # noqa: E402

CANDIDATE_PROMPT_VERSION = "candidate-next-v1"
REGRESSED_PROMPT_VERSION = "candidate-next-regressed"
REGRESSED_CASE_IDS = {"golden-0001", "golden-0039", "golden-0057"}
REGRESSED_SENTENCE = "This was confirmed in the latest handbook revision."


def _reorder_before(sentence: str) -> str | None:
    m = re.match(r"^(.*?)(\s+before\s+[^.]+)(\.)$", sentence)
    if not m:
        return None
    head, tail, dot = m.group(1), m.group(2).strip()[len("before "):], m.group(3)
    return f"{tail[0].upper()}{tail[1:]}, {head[0].lower()}{head[1:]}{dot}"


def _reorder_within(sentence: str) -> str | None:
    m = re.match(r"^(.*?)(\s+within\s+[^.]+)(\.)$", sentence)
    if not m:
        return None
    head, tail, dot = m.group(1), m.group(2).strip()[len("within "):], m.group(3)
    return f"Within {tail}, {head[0].lower()}{head[1:]}{dot}"


def _reorder_above(sentence: str) -> str | None:
    m = re.match(r"^(.*?)(\s+above\s+[^.]+)(\.)$", sentence)
    if not m:
        return None
    head, tail, dot = m.group(1), m.group(2).strip()[len("above "):], m.group(3)
    return f"Above {tail}, {head[0].lower()}{head[1:]}{dot}"


def _reorder_comma(sentence: str) -> str | None:
    parts = sentence.split(", ", 1)
    if len(parts) != 2 or not parts[1].endswith("."):
        return None
    head, tail = parts
    return f"{tail[0].upper()}{tail[1:]}, {head[0].lower()}{head[1:]}"


TRANSFORMS = [_reorder_before, _reorder_within, _reorder_above, _reorder_comma]


def paraphrase_answer(answer: str) -> str:
    """Token-preserving paraphrase: clause reordering only.

    Each transform reorders clauses without adding, removing, or replacing a
    single content token, so the candidate's heuristic scores stay within the
    migration tolerance bands by construction. Abstentions are kept verbatim
    because an abstention is not a paraphrasable statement.
    """
    out: list[str] = []
    for sentence in split_sentences(answer):
        if not sentence.strip() or is_abstention(sentence):
            out.append(sentence)
            continue
        clean = strip_citations(sentence)
        cited = re.findall(r"\[([A-Z]{2,4}-\d{4}-\d{2}#\d+)\]", sentence)
        moved = None
        for transform in TRANSFORMS:
            moved = transform(clean)
            if moved is not None:
                break
        body = moved if moved is not None else clean
        suffix = (" " + " ".join(f"[{c}]" for c in cited)) if cited else ""
        out.append(body + suffix)
    return " ".join(out)


def slim_dump(traces: list[TraceRecord]) -> str:
    """Serialize traces without the optional claims field.

    Claims are recomputed on replay, so the committed fixtures carry only the
    recorded fields the book's trace schema lists: question, prompt_version,
    retrieved ids and scores, answer, citations, per-layer scores, gate
    decision, and token usage.
    """
    lines = []
    for trace in traces:
        record = trace.model_dump()
        record.pop("claims")
        lines.append(TraceRecord.model_validate(record).model_dump_json())
    return "\n".join(lines) + "\n"


def main() -> int:
    thresholds = load_thresholds()
    profile = thresholds.profiles[thresholds.active_profile]
    corpus = load_corpus()
    golden = [
        GoldenCase.model_validate_json(line)
        for line in golden_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    run = runner.run_mock(golden, corpus, REPO_ROOT / "data/prompts/answer_v1.txt", profile)
    violations = runner.evaluate_ci_gates(run, golden, thresholds.ci_gates, None)
    if violations:
        print("baseline run fails the merge gates; fix before regenerating", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    runner.write_baseline(run, REPO_ROOT / "baselines/metrics_baseline.json", "2026-08-30T00:00:00Z")

    baseline_dir = REPO_ROOT / "data/traces/baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "traces_v1.jsonl").write_text(slim_dump(runner.build_traces(run)), encoding="utf-8")

    baseline_traces = runner.load_traces(baseline_dir / "traces_v1.jsonl")
    replayed = runner.run_replay(golden, corpus, baseline_traces, profile)
    if replayed.replay_mismatches:
        print("baseline traces do not replay cleanly", file=sys.stderr)
        return 1

    candidate = []
    for trace in baseline_traces:
        moved = trace.model_copy(deep=True)
        moved.answer = paraphrase_answer(trace.answer)
        moved.prompt_version = CANDIDATE_PROMPT_VERSION
        candidate.append(moved)

    replay = runner.run_replay(golden, corpus, candidate, profile)
    baseline = runner.load_baseline(REPO_ROOT / "baselines/metrics_baseline.json")
    tolerances = thresholds.migration_tolerances
    for metric in (
        "faithfulness", "answer_relevance", "claim_grounding",
        "context_precision", "context_recall", "recall_at_5",
    ):
        delta = replay.overall[metric] - baseline.overall[metric]
        if abs(delta) > getattr(tolerances, metric):
            print(f"candidate delta out of tolerance: {metric} {delta:+.3f}", file=sys.stderr)
            return 1
    changed = [r.case_id for r in replay.results if baseline.per_case[r.case_id].decision != r.decision]
    if changed:
        print(f"candidate changed decisions: {changed}", file=sys.stderr)
        return 1

    fixture_dir = REPO_ROOT / "data/traces/candidate_fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "traces_candidate_v1.jsonl").write_text(
        "\n".join(t.model_dump_json() for t in candidate) + "\n", encoding="utf-8"
    )

    regressed = []
    for trace in candidate:
        record = trace.model_copy(deep=True)
        if record.case_id in REGRESSED_CASE_IDS:
            record.answer = record.answer + " " + REGRESSED_SENTENCE
            record.prompt_version = REGRESSED_PROMPT_VERSION
        regressed.append(record)
    (fixture_dir / "traces_candidate_regressed.jsonl").write_text(
        "\n".join(t.model_dump_json() for t in regressed) + "\n", encoding="utf-8"
    )

    bad = runner.run_replay(
        golden, corpus, [t for t in regressed if t.case_id in REGRESSED_CASE_IDS], profile
    )
    for result in bad.results:
        if result.faithfulness >= 0.90:
            print(f"regressed case {result.case_id} did not drop below 0.90", file=sys.stderr)
            return 1

    print("fixtures regenerated: baseline, traces_v1, candidate_v1, candidate_regressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
