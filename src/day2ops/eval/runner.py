"""Evaluation runner: mock, replay, and live modes plus CI gate evaluation.

Single responsibility: orchestrate the five layers over the golden dataset
and decide whether the run passes the merge gates. Constraints: the mock and
replay paths are fully offline and deterministic; the evaluation role is a
non-security role, so restricted documents are filtered from retrieval before
scoring, mirroring Layer 7 classification filtering; quarantined corpus
chunks are reported, never silently dropped.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from day2ops.config import CIGates, ThresholdProfile
from day2ops.corpus.loader import Corpus
from day2ops.corpus.retrieval import BM25Retriever
from day2ops.eval.gate import apply_gate
from day2ops.eval.grounding import check_claims
from day2ops.eval.heuristics import score_ragas_metrics
from day2ops.eval.mock_generator import MockGenerator, load_answer_prompt
from day2ops.eval.retrieval_metrics import score_retrieval
from day2ops.eval.sufficiency import assess_sufficiency
from day2ops.schemas import (
    CaseEvaluation,
    CaseStatus,
    EvaluationMode,
    EvalRunResult,
    GateDecision,
    GoldenCase,
    PromptPersona,
    RetrievedChunk,
    TokenUsage,
    TraceRecord,
)

ROLE_ALLOWED_CLASSIFICATIONS = {"public", "internal"}
METRICS = [
    "faithfulness", "answer_relevance", "claim_grounding", "context_precision",
    "context_recall", "recall_at_5", "precision_at_5", "mrr",
]


class BaselinePerCase(BaseModel):
    decision: GateDecision
    faithfulness: float
    claim_grounding: float
    recall_at_5: float


class Baseline(BaseModel):
    generated_at: str
    mode: str
    profile: str
    prompt_version: str
    case_count: int
    aggregates: dict[str, dict[str, float]]
    overall: dict[str, float]
    per_case: dict[str, BaselinePerCase]


def filter_restricted(
    retrieved: list[RetrievedChunk], corpus: Corpus
) -> tuple[list[RetrievedChunk], list[str]]:
    chunks = corpus.chunks_by_id()
    kept, dropped = [], []
    for rc in retrieved:
        chunk = chunks.get(rc.chunk_id)
        if chunk is not None and chunk.classification not in ROLE_ALLOWED_CLASSIFICATIONS:
            dropped.append(rc.chunk_id)
        else:
            kept.append(rc)
    return kept, dropped


def _token_usage(question: str, retrieved_words: int, answer: str) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=40 + len(question.split()) + retrieved_words,
        completion_tokens=len(answer.split()) + 3,
    )


def _score_case(
    case: GoldenCase,
    retrieved: list[RetrievedChunk],
    dropped: list[str],
    answer: str,
    citations: list[str],
    persona: PromptPersona,
    prompt_version: str,
    corpus: Corpus,
    profile: ThresholdProfile,
) -> CaseEvaluation:
    chunks_by_id = corpus.chunks_by_id()
    sufficiency = assess_sufficiency(
        case.question, retrieved, chunks_by_id, corpus.department_docs(), corpus.docs_by_id()
    )
    ragas = score_ragas_metrics(case, answer, citations, retrieved, chunks_by_id)
    grounding = check_claims(answer, retrieved, chunks_by_id)
    gate = apply_gate(sufficiency, grounding, ragas.faithfulness, case.risk_tier, profile)
    retrieval = score_retrieval(case, [rc.chunk_id for rc in retrieved])
    words = sum(
        len(chunks_by_id[rc.chunk_id].text.split()) for rc in retrieved if rc.chunk_id in chunks_by_id
    )
    return CaseEvaluation(
        case_id=case.case_id,
        question=case.question,
        risk_tier=case.risk_tier,
        status=case.status,
        decision=gate.decision,
        gate_reason=gate.reason,
        rule_fired=gate.rule_fired,
        retrieved=retrieved,
        dropped_restricted=dropped,
        answer=answer,
        citations=citations,
        sufficiency=sufficiency.sufficiency,
        recall_at_5=retrieval.recall_at_5,
        precision_at_5=retrieval.precision_at_5,
        mrr=retrieval.mrr,
        context_precision=ragas.context_precision,
        context_recall=ragas.context_recall,
        faithfulness=ragas.faithfulness,
        answer_relevance=ragas.answer_relevance,
        claim_grounding=grounding.claim_grounding,
        unsupported_claims=grounding.unsupported,
        claims=grounding.claims,
        token_usage=_token_usage(case.question, words, answer),
        persona=persona,
        prompt_version=prompt_version,
    )


def _aggregate(
    results: list[CaseEvaluation],
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    aggregates: dict[str, dict[str, float]] = {}
    for tier in ("low", "medium", "high"):
        rows = [r for r in results if r.risk_tier.value == tier]
        aggregates[tier] = {
            metric: (sum(getattr(r, metric) for r in rows) / len(rows)) if rows else 1.0
            for metric in METRICS
        }
    overall = {
        metric: sum(getattr(r, metric) for r in results) / len(results) if results else 1.0
        for metric in METRICS
    }
    return aggregates, overall


def run_mock(
    golden: list[GoldenCase], corpus: Corpus, prompt_path: Path, profile: ThresholdProfile
) -> EvalRunResult:
    prompt = load_answer_prompt(prompt_path)
    generator = MockGenerator(prompt)
    retriever = BM25Retriever(corpus.index_chunks)
    chunks_by_id = corpus.chunks_by_id()
    docs_by_id = corpus.docs_by_id()
    results = []
    for case in golden:
        retrieved, dropped = filter_restricted(retriever.retrieve(case.question), corpus)
        sufficiency = assess_sufficiency(
            case.question, retrieved, chunks_by_id, corpus.department_docs(), docs_by_id
        )
        generated = generator.generate(case.question, retrieved, chunks_by_id, docs_by_id, sufficiency)
        results.append(
            _score_case(
                case, retrieved, dropped, generated.answer, generated.citations,
                generated.persona, generated.prompt_version, corpus, profile,
            )
        )
    aggregates, overall = _aggregate(results)
    return EvalRunResult(
        mode=EvaluationMode.MOCK, profile=profile.name, prompt_version=prompt.version,
        case_count=len(results), results=results, aggregates=aggregates, overall=overall,
        corpus_quarantined=corpus.quarantined_chunk_ids,
    )


def load_traces(path: Path) -> list[TraceRecord]:
    return [
        TraceRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run_replay(
    golden: list[GoldenCase], corpus: Corpus, traces: list[TraceRecord], profile: ThresholdProfile
) -> EvalRunResult:
    by_case = {t.case_id: t for t in traces}
    results = []
    mismatches = []
    for case in golden:
        trace = by_case.get(case.case_id)
        if trace is None:
            continue
        results.append(
            _score_case(
                case, trace.retrieved, [], trace.answer, trace.citations,
                trace.persona, trace.prompt_version, corpus, profile,
            )
        )
        if results[-1].decision != trace.gate_decision:
            mismatches.append(case.case_id)
    aggregates, overall = _aggregate(results)
    return EvalRunResult(
        mode=EvaluationMode.REPLAY, profile=profile.name,
        prompt_version=traces[0].prompt_version if traces else "unknown",
        case_count=len(results), results=results, aggregates=aggregates, overall=overall,
        corpus_quarantined=corpus.quarantined_chunk_ids, replay_mismatches=mismatches,
    )


def build_traces(run: EvalRunResult) -> list[TraceRecord]:
    traces = []
    for r in run.results:
        traces.append(
            TraceRecord(
                case_id=r.case_id, question=r.question, prompt_version=r.prompt_version,
                persona=r.persona, retrieved=r.retrieved, answer=r.answer, citations=r.citations,
                sufficiency=r.sufficiency,
                metrics={
                    "recall_at_5": r.recall_at_5, "precision_at_5": r.precision_at_5, "mrr": r.mrr,
                    "context_precision": r.context_precision, "context_recall": r.context_recall,
                    "faithfulness": r.faithfulness, "answer_relevance": r.answer_relevance,
                    "claim_grounding": r.claim_grounding,
                },
                claims=r.claims, gate_decision=r.decision, gate_reason=r.gate_reason,
                risk_tier=r.risk_tier, status=r.status, token_usage=r.token_usage,
            )
        )
    return traces


def write_baseline(run: EvalRunResult, path: Path, generated_at: str) -> None:
    baseline = Baseline(
        generated_at=generated_at, mode=run.mode.value, profile=run.profile,
        prompt_version=run.prompt_version, case_count=run.case_count,
        aggregates=run.aggregates, overall=run.overall,
        per_case={
            r.case_id: BaselinePerCase(
                decision=r.decision, faithfulness=r.faithfulness,
                claim_grounding=r.claim_grounding, recall_at_5=r.recall_at_5,
            )
            for r in run.results
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(baseline.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> Baseline:
    return Baseline.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_ci_gates(
    run: EvalRunResult,
    golden: list[GoldenCase],
    gates: CIGates,
    baseline: Baseline | None = None,
) -> list[str]:
    violations: list[str] = []
    cases = {c.case_id: c for c in golden}
    for tier, values in run.aggregates.items():
        if values["faithfulness"] < gates.faithfulness_min_any_tier:
            violations.append(
                f"faithfulness on {tier} tier {values['faithfulness']:.3f} below "
                f"{gates.faithfulness_min_any_tier}"
            )
    if run.aggregates["high"]["faithfulness"] < gates.faithfulness_min_high_risk:
        violations.append(
            f"high-risk faithfulness {run.aggregates['high']['faithfulness']:.3f} below "
            f"{gates.faithfulness_min_high_risk}"
        )
    for r in run.results:
        case = cases.get(r.case_id)
        if case is None or not case.should_answer:
            continue
        if r.claim_grounding < gates.claim_grounding_min:
            violations.append(
                f"{r.case_id}: claim grounding {r.claim_grounding:.3f} below {gates.claim_grounding_min}"
            )
        if r.unsupported_claims > 0:
            violations.append(
                f"{r.case_id}: {r.unsupported_claims} unsupported claim(s) on a should-answer case"
            )
    if run.overall["recall_at_5"] < gates.recall_at_5_min:
        violations.append(
            f"aggregate recall@5 {run.overall['recall_at_5']:.3f} below {gates.recall_at_5_min}"
        )
    if baseline is not None:
        by_id = {r.case_id: r for r in run.results}
        for case in golden:
            if case.status != CaseStatus.PRODUCTION_FROZEN:
                continue
            base = baseline.per_case.get(case.case_id)
            current = by_id.get(case.case_id)
            if base is not None and current is not None and base.decision != current.decision:
                violations.append(
                    f"{case.case_id}: PRODUCTION-FROZEN decision changed from "
                    f"{base.decision.value} to {current.decision.value}"
                )
        for r in run.results:
            base = baseline.per_case.get(r.case_id)
            if base is None:
                continue
            if (
                base.decision in {GateDecision.ABSTAIN, GateDecision.BLOCK, GateDecision.HUMAN_REVIEW}
                and r.decision in {GateDecision.ANSWER, GateDecision.QUALIFIED_ANSWER}
            ):
                violations.append(
                    f"{r.case_id}: false pass on {r.risk_tier.value} risk "
                    f"(baseline {base.decision.value}, now {r.decision.value})"
                )
    return violations
