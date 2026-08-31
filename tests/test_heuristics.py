"""Behavior tests for the Ragas-aligned heuristic scores."""
from __future__ import annotations

from day2ops.eval.heuristics import score_ragas_metrics
from day2ops.schemas import Chunk, GoldenCase, RetrievedChunk


CURRENT = Chunk(
    chunk_id="HR-2026-03#1", doc_id="HR-2026-03",
    text="Employees must provide 90 days of written notice before terminating employment.",
)
CASE = GoldenCase(
    case_id="t", question="How many days of notice must an employee give?",
    risk_tier="high", expected_answer="90 days", expected_doc_ids=["HR-2026-03"],
)
RETRIEVED = [RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)]
BY_ID = {"HR-2026-03#1": CURRENT}


def test_faithful_answer_scores_high_faithfulness() -> None:
    answer = "Employees must provide 90 days of written notice before terminating employment. [HR-2026-03#1]"
    m = score_ragas_metrics(CASE, answer, ["HR-2026-03#1"], RETRIEVED, BY_ID)
    assert m.faithfulness >= 0.95
    assert m.context_recall == 1.0
    assert m.context_precision == 1.0


def test_fabricated_answer_scores_low_faithfulness() -> None:
    answer = "Employees must provide 90 days of written notice. This was confirmed in the latest handbook revision."
    m = score_ragas_metrics(CASE, answer, [], RETRIEVED, BY_ID)
    assert m.faithfulness < 0.90
    assert m.context_precision == 0.0


def test_answer_relevance_uses_expected_answer() -> None:
    good = score_ragas_metrics(CASE, "Employees must provide 90 days of written notice. [HR-2026-03#1]", ["HR-2026-03#1"], RETRIEVED, BY_ID)
    bad = score_ragas_metrics(CASE, "The cafeteria opens at noon. [HR-2026-03#1]", ["HR-2026-03#1"], RETRIEVED, BY_ID)
    assert good.answer_relevance > bad.answer_relevance
    assert good.answer_relevance >= 0.80


def test_abstention_is_vacuously_faithful() -> None:
    m = score_ragas_metrics(CASE, "I cannot answer this question from the available policies.", [], RETRIEVED, BY_ID)
    assert m.faithfulness == 1.0
