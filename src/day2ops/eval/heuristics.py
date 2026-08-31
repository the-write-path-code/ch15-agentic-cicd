"""Layer 2: Ragas-aligned heuristic scores (mock judge).

Single responsibility: compute context_precision, context_recall,
faithfulness, and answer_relevance deterministically. The real Ragas library
is never imported here; it is an optional CI-only judge (see ragas_ci).
Constraints: context metrics compare citations to expected documents;
faithfulness is answer-level token grounding against retrieved context and is
1.0 for abstentions (no statements, mirroring Ragas); answer_relevance blends
question and expected-answer token coverage.
"""
from __future__ import annotations

from day2ops.eval.textutils import (
    content_tokens,
    is_statement,
    split_sentences,
    strip_citations,
    token_coverage,
)
from day2ops.schemas import Chunk, GoldenCase, RagasMetrics, RetrievedChunk


def _doc_of(chunk_id: str) -> str:
    return chunk_id.split("#")[0]


def context_recall(case: GoldenCase, citations: list[str]) -> float:
    expected = set(case.expected_doc_ids)
    if not expected:
        return 1.0
    cited = {_doc_of(c) for c in citations}
    return len(expected & cited) / len(expected)


def context_precision(case: GoldenCase, citations: list[str]) -> float:
    expected = set(case.expected_doc_ids)
    if not citations:
        return 1.0 if not expected else 0.0
    hits = sum(1 for c in citations if _doc_of(c) in expected)
    return hits / len(citations)


def faithfulness(answer: str, retrieved: list[RetrievedChunk], chunks_by_id: dict[str, Chunk]) -> float:
    statements = [s for s in split_sentences(answer) if is_statement(s)]
    if not statements:
        return 1.0
    context_tokens: set[str] = set()
    for rc in retrieved:
        chunk = chunks_by_id.get(rc.chunk_id)
        if chunk is not None:
            context_tokens |= content_tokens(chunk.text)
    scores: list[float] = []
    for statement in statements:
        tokens = content_tokens(strip_citations(statement))
        if not tokens:
            continue
        scores.append(len(tokens & context_tokens) / len(tokens))
    if not scores:
        return 1.0
    return sum(scores) / len(scores)


def answer_relevance(case: GoldenCase, answer: str) -> float:
    return 0.5 * token_coverage(case.question, answer) + 0.5 * token_coverage(
        case.expected_answer, answer
    )


def score_ragas_metrics(
    case: GoldenCase,
    answer: str,
    citations: list[str],
    retrieved: list[RetrievedChunk],
    chunks_by_id: dict[str, Chunk],
) -> RagasMetrics:
    return RagasMetrics(
        context_precision=context_precision(case, citations),
        context_recall=context_recall(case, citations),
        faithfulness=faithfulness(answer, retrieved, chunks_by_id),
        answer_relevance=answer_relevance(case, answer),
    )
