"""Behavior tests for the deterministic claim checker."""
from __future__ import annotations

from day2ops.eval.grounding import check_claims
from day2ops.schemas import Chunk, ClaimVerdict, RetrievedChunk


def _chunk(chunk_id: str, text: str, superseded: bool = False) -> Chunk:
    return Chunk(chunk_id=chunk_id, doc_id=chunk_id.split("#")[0], text=text, superseded=superseded)


CURRENT = _chunk("HR-2026-03#1", "Employees must provide 90 days of written notice before terminating employment.")
STALE = _chunk("HR-2024-11#1", "Employees must provide 60 days of written notice.", superseded=True)


def test_extracted_sentence_is_supported() -> None:
    answer = "Employees must provide 90 days of written notice before terminating employment. [HR-2026-03#1]"
    result = check_claims(answer, [RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)], {"HR-2026-03#1": CURRENT})
    assert result.claims[0].verdict == ClaimVerdict.SUPPORTED
    assert result.claim_grounding == 1.0


def test_fabricated_sentence_is_unsupported() -> None:
    answer = "The notice period is 90 days. This was confirmed in the latest handbook revision."
    result = check_claims(
        answer,
        [RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)],
        {"HR-2026-03#1": CURRENT},
    )
    verdicts = [c.verdict for c in result.claims]
    assert ClaimVerdict.UNSUPPORTED in verdicts
    assert result.claim_grounding < 0.95


def test_stale_value_contradicted_by_current_evidence() -> None:
    answer = "Employees must provide 60 days of written notice."
    result = check_claims(
        answer,
        [RetrievedChunk(chunk_id="HR-2026-03#1", score=11.0), RetrievedChunk(chunk_id="HR-2024-11#1", score=13.0)],
        {"HR-2026-03#1": CURRENT, "HR-2024-11#1": STALE},
    )
    assert result.claims[0].verdict == ClaimVerdict.CONTRADICTED


def test_cited_stale_sentence_stays_supported() -> None:
    answer = "Employees must provide 60 days of written notice. [HR-2024-11#1]"
    result = check_claims(
        answer,
        [RetrievedChunk(chunk_id="HR-2026-03#1", score=11.0), RetrievedChunk(chunk_id="HR-2024-11#1", score=13.0)],
        {"HR-2026-03#1": CURRENT, "HR-2024-11#1": STALE},
    )
    assert result.claims[0].verdict == ClaimVerdict.SUPPORTED


def test_abstention_sentence_is_not_a_claim() -> None:
    answer = "I cannot answer this question from the available policies."
    result = check_claims(answer, [RetrievedChunk(chunk_id="HR-2026-03#1", score=10.0)], {"HR-2026-03#1": CURRENT})
    assert result.claims == []
    assert result.claim_grounding == 1.0
