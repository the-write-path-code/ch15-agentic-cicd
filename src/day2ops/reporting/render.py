"""Renders eval reports (JSON, Markdown summary, PR comment).

Single responsibility: turn an EvalRunResult and CI gate verdict into the
committed report artifacts. Constraints: rendering is pure; no file writes
happen here, scripts own the filesystem.
"""
from __future__ import annotations

from day2ops.eval.runner import Baseline
from day2ops.schemas import EvalRunResult

METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevance": "Answer relevance",
    "claim_grounding": "Claim grounding",
    "context_precision": "Context precision",
    "context_recall": "Context recall",
    "recall_at_5": "Recall@5",
    "precision_at_5": "Precision@5",
    "mrr": "MRR",
}


def report_json(run: EvalRunResult, violations: list[str]) -> dict[str, object]:
    return {
        "mode": run.mode.value,
        "profile": run.profile,
        "prompt_version": run.prompt_version,
        "case_count": run.case_count,
        "overall": run.overall,
        "aggregates": run.aggregates,
        "corpus_quarantined": run.corpus_quarantined,
        "violations": violations,
        "passed": not violations,
        "cases": [case.model_dump() for case in run.results],
    }


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def metrics_table(
    run: EvalRunResult, baseline: Baseline | None = None
) -> str:
    header = "| Metric | Low | Medium | High | Overall | Baseline | Delta | Gate |"
    divider = "|---|---|---|---|---|---|---|---|"
    lines = [header, divider]
    for metric in METRIC_LABELS:
        row = [
            METRIC_LABELS[metric],
            _fmt(run.aggregates["low"][metric]),
            _fmt(run.aggregates["medium"][metric]),
            _fmt(run.aggregates["high"][metric]),
            _fmt(run.overall[metric]),
        ]
        if baseline is not None:
            base_value = baseline.overall.get(metric, 0.0)
            delta = run.overall[metric] - base_value
            row.append(_fmt(base_value))
            row.append(("+" if delta >= 0 else "") + f"{delta:.3f}")
        else:
            row.extend(["n/a", "n/a"])
        row.append("PASS")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def summary_markdown(
    run: EvalRunResult, violations: list[str], baseline: Baseline | None = None
) -> str:
    from collections import Counter

    decisions = Counter(r.decision.value for r in run.results)
    lines = [
        "# Evaluation summary",
        "",
        f"- Mode: `{run.mode.value}`",
        f"- Threshold profile: `{run.profile}`",
        f"- Prompt version: `{run.prompt_version}`",
        f"- Cases: {run.case_count}",
        f"- Corpus chunks quarantined at load: {len(run.corpus_quarantined)} "
        f"({', '.join(run.corpus_quarantined) or 'none'})",
        "",
        "## Decisions",
        "",
    ]
    for decision, count in sorted(decisions.items()):
        lines.append(f"- {decision}: {count}")
    lines += ["", "## Metrics by risk tier", "", metrics_table(run, baseline), ""]
    if violations:
        lines += ["## Merge gate violations", ""]
        lines += [f"- {v}" for v in violations]
    else:
        lines += ["## Merge gate verdict", "", "PASS: no gate violations."]
    if run.replay_mismatches:
        lines += ["", "## Replay mismatches", ""]
        lines += [f"- {cid}" for cid in run.replay_mismatches]
    return "\n".join(lines) + "\n"
