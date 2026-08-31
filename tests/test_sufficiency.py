"""Behavior tests for evidence sufficiency classification."""
from __future__ import annotations

from day2ops.eval.sufficiency import assess_sufficiency
from day2ops.schemas import Chunk, PolicyDocument, RetrievedChunk, SufficiencyClass


def _chunk(chunk_id: str, text: str, superseded: bool = False, scope: str = "all") -> Chunk:
    return Chunk(
        chunk_id=chunk_id, doc_id=chunk_id.split("#")[0], text=text,
        superseded=superseded, department_scope=scope,
    )


def _run(question: str, chunks: list[Chunk], score: float = 10.0,
         dept_docs: dict[str, list[str]] | None = None) -> SufficiencyClass:
    retrieved = [RetrievedChunk(chunk_id=c.chunk_id, score=score) for c in chunks]
    by_id = {c.chunk_id: c for c in chunks}
    docs = {
        c.doc_id: PolicyDocument(
            doc_id=c.doc_id, title="t", classification="internal",
            department_scope=c.department_scope, effective_date="2026-01-01",
        )
        for c in chunks
    }
    result = assess_sufficiency(question, retrieved, by_id, dept_docs or {}, docs)
    return result.sufficiency


def test_no_relevant_evidence_is_insufficient() -> None:
    cls = _run("What is the tuition budget?", [_chunk("HR-2026-01#1", "Expense reports are due within 30 days.")], score=2.0)
    assert cls == SufficiencyClass.INSUFFICIENT


def test_conflicting_authorities_detected_on_remote_work() -> None:
    hr = _chunk("HR-2026-07#1", "Department heads may approve remote work requests for their teams.")
    sec = _chunk("SEC-2026-04#1", "All remote work requests must be approved in writing by the Chief Operating Officer.")
    assert _run("Who approves remote work requests?", [hr, sec]) == SufficiencyClass.CONFLICTING


def test_tiered_purchase_authorities_are_not_a_conflict() -> None:
    capex = _chunk("HR-2026-09#1", "Purchases under $10,000 require manager approval. Purchases above $25,000 require Vice President approval.")
    assert _run("Whose approval is required for a $30,000 purchase?", [capex]) == SufficiencyClass.SUFFICIENT


def test_all_superseded_evidence_is_partial() -> None:
    stale = _chunk("HR-2024-11#1", "Employees must provide 60 days of written notice.", superseded=True)
    assert _run("How much notice is required?", [stale]) == SufficiencyClass.PARTIAL


def test_department_exception_missing_is_partial() -> None:
    general = _chunk("HR-2026-03#1", "The 90-day notice period applies to all departments.")
    scoped = _chunk("HR-2026-05#1", "Field Operations employees must provide 45 days of notice.", scope="Field Operations")
    result = _run("How much notice for the Field Operations team?", [general], dept_docs={"Field Operations": ["HR-2026-05"]})
    assert result == SufficiencyClass.PARTIAL
    result = _run("How much notice for the Field Operations team?", [general, scoped], dept_docs={"Field Operations": ["HR-2026-05"]})
    assert result == SufficiencyClass.SUFFICIENT


def test_current_evidence_sufficient() -> None:
    current = _chunk("HR-2026-03#1", "Employees must provide 90 days of written notice.")
    assert _run("How much notice is required?", [current]) == SufficiencyClass.SUFFICIENT
