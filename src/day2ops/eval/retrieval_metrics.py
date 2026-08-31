"""Layer 1: deterministic retrieval metrics (recall@5, precision@5, MRR).

Single responsibility: score retrieved chunk ids against the golden expected
document ids. Constraints: recall is 1.0 when a case expects no documents
(vacuously all found); skipped or quarantined cases stay in the denominator
they came from.
"""
from __future__ import annotations

from day2ops.schemas import GoldenCase, RetrievalMetrics


def _doc_of(chunk_id: str) -> str:
    return chunk_id.split("#")[0]


def recall_at_k(case: GoldenCase, retrieved_ids: list[str], k: int = 5) -> float:
    expected = set(case.expected_doc_ids)
    if not expected:
        return 1.0
    got = {_doc_of(cid) for cid in retrieved_ids[:k]}
    return len(expected & got) / len(expected)


def precision_at_k(case: GoldenCase, retrieved_ids: list[str], k: int = 5) -> float:
    expected = set(case.expected_doc_ids)
    top = [_doc_of(cid) for cid in retrieved_ids[:k]]
    if not top:
        return 1.0 if not expected else 0.0
    hits = sum(1 for doc in top if doc in expected)
    return hits / len(top)


def mrr(case: GoldenCase, retrieved_ids: list[str]) -> float:
    expected = set(case.expected_doc_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if _doc_of(cid) in expected:
            return 1.0 / rank
    return 0.0


def score_retrieval(case: GoldenCase, retrieved_ids: list[str]) -> RetrievalMetrics:
    return RetrievalMetrics(
        recall_at_5=recall_at_k(case, retrieved_ids),
        precision_at_5=precision_at_k(case, retrieved_ids),
        mrr=mrr(case, retrieved_ids),
    )
