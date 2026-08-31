"""Layer 4: deterministic evidence sufficiency.

Single responsibility: classify retrieved evidence as SUFFICIENT, PARTIAL,
INSUFFICIENT, or CONFLICTING for a question. Constraints: relevance is a BM25
score threshold; a conflict is two different unconditional approval
authorities for the same action across different documents, and it only
matters when the question asks about approval; stale evidence (every relevant
chunk superseded) and missing department exceptions both yield PARTIAL.
"""
from __future__ import annotations

import re

from day2ops.schemas import Chunk, PolicyDocument, RetrievedChunk, SufficiencyClass, SufficiencyResult

RELEVANCE_THRESHOLD = 4.0
APPROVAL_INTENT_RE = re.compile(r"approv", re.IGNORECASE)
DEPT_PATTERNS = [
    re.compile(r"for (?:the )?(Field Operations|Security)\b"),
    re.compile(r"\b(?:does|do|is|are|can|in)\s+(?:the\s+)?(Field Operations|Security)\b"),
]
ACTION_PHRASES = ["remote work", "purchase", "access"]
AUTHORITY_PHRASES = [
    "Chief Operating Officer",
    "Department heads",
    "Vice President",
    "Chief Financial Officer",
    "Director",
    "manager",
    "system owners",
    "CISO",
]


def _authority_pairs(chunk: Chunk) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", chunk.text):
        if any(ch.isdigit() for ch in sentence):
            continue
        low = sentence.lower()
        for action in ACTION_PHRASES:
            if action in low:
                for authority in AUTHORITY_PHRASES:
                    if authority.lower() in low:
                        pairs.add((action, authority))
    return pairs


def _mentioned_department(question: str) -> str | None:
    for pattern in DEPT_PATTERNS:
        match = pattern.search(question)
        if match is not None:
            return match.group(1)
    return None


def assess_sufficiency(
    question: str,
    retrieved: list[RetrievedChunk],
    chunks_by_id: dict[str, Chunk],
    department_docs: dict[str, list[str]],
    docs_by_id: dict[str, PolicyDocument],
    relevance_threshold: float = RELEVANCE_THRESHOLD,
) -> SufficiencyResult:
    relevant = [rc for rc in retrieved if rc.score >= relevance_threshold]
    relevant_chunks = [chunks_by_id[rc.chunk_id] for rc in relevant if rc.chunk_id in chunks_by_id]
    if not relevant_chunks:
        return SufficiencyResult(
            sufficiency=SufficiencyClass.INSUFFICIENT,
            reason="no retrieved chunk reaches the relevance threshold",
        )
    if APPROVAL_INTENT_RE.search(question):
        pairs_by_doc: dict[str, set[tuple[str, str]]] = {}
        for chunk in relevant_chunks:
            pairs_by_doc.setdefault(chunk.doc_id, set()).update(_authority_pairs(chunk))
        actions: dict[str, set[str]] = {}
        action_docs: dict[str, set[str]] = {}
        for doc_id, pairs in pairs_by_doc.items():
            for action, authority in pairs:
                actions.setdefault(action, set()).add(authority)
                action_docs.setdefault(action, set()).add(doc_id)
        for action, authorities in actions.items():
            if len(authorities) > 1 and len(action_docs[action]) > 1:
                return SufficiencyResult(
                    sufficiency=SufficiencyClass.CONFLICTING,
                    reason=f"{action} approval authority conflicts across documents",
                    relevant_chunk_ids=[rc.chunk_id for rc in relevant],
                )
    if all(chunk.superseded for chunk in relevant_chunks):
        return SufficiencyResult(
            sufficiency=SufficiencyClass.PARTIAL,
            reason="all relevant evidence is superseded",
            relevant_chunk_ids=[rc.chunk_id for rc in relevant],
        )
    department = _mentioned_department(question)
    if department is not None:
        scoped = department_docs.get(department, [])
        present = {chunk.doc_id for chunk in relevant_chunks}
        if scoped and not any(doc_id in present for doc_id in scoped):
            return SufficiencyResult(
                sufficiency=SufficiencyClass.PARTIAL,
                reason=f"department-specific documents for {department} not retrieved",
                relevant_chunk_ids=[rc.chunk_id for rc in relevant],
            )
    return SufficiencyResult(
        sufficiency=SufficiencyClass.SUFFICIENT,
        reason="relevant current evidence retrieved",
        relevant_chunk_ids=[rc.chunk_id for rc in relevant],
    )
