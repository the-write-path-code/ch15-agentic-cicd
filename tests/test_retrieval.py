"""Behavior tests for BM25 retrieval and corpus quarantine."""
from __future__ import annotations

from day2ops.corpus.retrieval import BM25Retriever
from day2ops.eval.sufficiency import RELEVANCE_THRESHOLD
from day2ops.schemas import RiskTier


def test_notice_question_retrieves_current_policy(corpus, golden) -> None:
    case = next(c for c in golden if c.case_id == "golden-0001")
    retriever = BM25Retriever(corpus.index_chunks)
    retrieved = retriever.retrieve(case.question)
    ids = [rc.chunk_id for rc in retrieved]
    assert any(i.startswith("HR-2026-03") for i in ids)
    assert any(i.startswith("HR-2024-11") for i in ids)
    top = retrieved[0]
    assert top.chunk_id.startswith("HR-2024-11")
    assert top.score >= RELEVANCE_THRESHOLD


def test_miss_question_scores_below_relevance_threshold(corpus, golden) -> None:
    case = next(c for c in golden if c.case_id == "golden-0044" and c.risk_tier == RiskTier.MEDIUM)
    retriever = BM25Retriever(corpus.index_chunks)
    retrieved = retriever.retrieve(case.question)
    assert all(rc.score < RELEVANCE_THRESHOLD for rc in retrieved)


def test_poisoned_chunk_quarantined_at_load(corpus) -> None:
    assert corpus.quarantined_chunk_ids == ["HR-2026-10#3"]
    all_ids = {c.chunk_id for c in corpus.chunks}
    index_ids = {c.chunk_id for c in corpus.index_chunks}
    assert "HR-2026-10#3" in all_ids
    assert "HR-2026-10#3" not in index_ids
    assert len(corpus.chunks) == len(corpus.index_chunks) + len(corpus.quarantined_chunk_ids)


def test_retrieval_is_deterministic(corpus) -> None:
    retriever = BM25Retriever(corpus.index_chunks)
    first = retriever.retrieve("How much notice must an employee give?")
    second = retriever.retrieve("How much notice must an employee give?")
    assert [r.chunk_id for r in first] == [r.chunk_id for r in second]
