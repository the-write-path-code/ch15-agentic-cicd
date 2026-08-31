"""Corpus and golden dataset integrity tests."""
from __future__ import annotations

from day2ops.schemas import CaseStatus


def test_corpus_shape(corpus) -> None:
    assert len(corpus.documents) == 18
    doc_ids = {d.doc_id for d in corpus.documents}
    assert "HR-2026-04" not in doc_ids
    assert "HR-2024-11" in doc_ids
    assert "SEC-2026-02" in doc_ids


def test_superseded_flags_propagate_to_chunks(corpus) -> None:
    by_id = corpus.chunks_by_id()
    assert all(c.superseded for c in by_id.values() if c.doc_id == "HR-2024-11")
    assert not any(c.superseded for c in by_id.values() if c.doc_id == "HR-2026-03")


def test_restricted_document_is_restricted(corpus) -> None:
    doc = corpus.docs_by_id()["SEC-2026-02"]
    assert doc.classification == "restricted"
    assert doc.department_scope == "Security"


def test_golden_shape(golden) -> None:
    assert len(golden) == 60
    ids = [c.case_id for c in golden]
    assert len(set(ids)) == 60
    frozen = [c for c in golden if c.status == CaseStatus.PRODUCTION_FROZEN]
    assert len(frozen) == 12
    assert all(c.origin == "ch04-seed" for c in frozen)


def test_seed_includes_worked_examples(golden) -> None:
    ids = {c.case_id: c for c in golden}
    assert ids["golden-0001"].risk_tier.value == "high"
    assert ids["golden-0001"].expected_answer == "90 days"
    assert ids["golden-0003"].expected_doc_ids == ["HR-2026-09"]
