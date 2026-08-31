"""Layer 3: deterministic claim-level grounding with a pluggable judge hook.

Single responsibility: split answers into claims, assign each a ClaimVerdict
against cited (or, when uncited, all retrieved) evidence, and aggregate a
claim_grounding score. Constraints: heuristic verdicts are token-coverage and
numeric-consistency checks; a claim that asserts a value supported only by
superseded evidence while current evidence disagrees is CONTRADICTED;
claim_grounding is 1.0 when there are no substantive claims.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from day2ops.eval.textutils import CITATION_RE, content_tokens, is_abstention, split_sentences, strip_citations
from day2ops.schemas import Claim, ClaimVerdict, Chunk, GroundingResult, RetrievedChunk

UNIT_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(days?|hours?|weeks?|months?|years?|percent|%)\b", re.IGNORECASE)
COVERAGE_THRESHOLD = 0.5


def _normalize_unit(unit: str) -> str:
    unit = unit.lower().rstrip("s")
    return "percent" if unit == "%" else unit


def _unit_values(text: str) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for value, unit in UNIT_VALUE_RE.findall(text):
        values.setdefault(_normalize_unit(unit), set()).add(value)
    return values


def _heuristic_verdict(claim: str, evidence: list[Chunk]) -> ClaimVerdict:
    claim_tokens = content_tokens(claim)
    evidence_tokens: set[str] = set()
    for chunk in evidence:
        evidence_tokens |= content_tokens(chunk.text)
    for unit, values in _unit_values(claim).items():
        for value in values:
            supporting = [
                c for c in evidence if value in _unit_values(c.text).get(unit, set())
            ]
            if supporting and all(c.superseded for c in supporting):
                conflicting_current = [
                    c
                    for c in evidence
                    if not c.superseded and _unit_values(c.text).get(unit, set()) - {value}
                ]
                if conflicting_current:
                    return ClaimVerdict.CONTRADICTED
    coverage = len(claim_tokens & evidence_tokens) / len(claim_tokens) if claim_tokens else 1.0
    if coverage >= COVERAGE_THRESHOLD:
        return ClaimVerdict.SUPPORTED
    return ClaimVerdict.UNSUPPORTED


def check_claims(
    answer: str,
    retrieved: list[RetrievedChunk],
    chunks_by_id: dict[str, Chunk],
    judge: Callable[[str, list[str]], ClaimVerdict] | None = None,
) -> GroundingResult:
    claims: list[Claim] = []
    all_evidence = [chunks_by_id[rc.chunk_id] for rc in retrieved if rc.chunk_id in chunks_by_id]
    for sentence in split_sentences(answer):
        if is_abstention(sentence) or not content_tokens(strip_citations(sentence)):
            continue
        cited_ids = CITATION_RE.findall(sentence)
        clean = strip_citations(sentence)
        evidence = [chunks_by_id[c] for c in cited_ids if c in chunks_by_id] or all_evidence
        if judge is not None:
            verdict = judge(clean, [chunk.text for chunk in evidence])
        else:
            verdict = _heuristic_verdict(clean, evidence)
        claims.append(
            Claim(text=clean, verdict=verdict, evidence_chunk_ids=[c.chunk_id for c in evidence])
        )
    supported = sum(1 for c in claims if c.verdict == ClaimVerdict.SUPPORTED)
    unsupported = sum(1 for c in claims if c.verdict == ClaimVerdict.UNSUPPORTED)
    contradicted = sum(1 for c in claims if c.verdict == ClaimVerdict.CONTRADICTED)
    not_applicable = sum(1 for c in claims if c.verdict == ClaimVerdict.NOT_APPLICABLE)
    denominator = supported + unsupported + contradicted
    grounding = supported / denominator if denominator else 1.0
    return GroundingResult(
        claim_grounding=grounding,
        claims=claims,
        supported=supported,
        unsupported=unsupported,
        contradicted=contradicted,
        not_applicable=not_applicable,
    )
