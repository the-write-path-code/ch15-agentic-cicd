"""Behavior tests for the Chapter 4 rule cascade."""
from __future__ import annotations

import pytest

from day2ops.config import ThresholdProfile
from day2ops.eval.gate import apply_gate
from day2ops.schemas import (
    Claim,
    ClaimVerdict,
    GateDecision,
    GroundingResult,
    RiskTier,
    SufficiencyClass,
    SufficiencyResult,
)


def _suff(cls: SufficiencyClass) -> SufficiencyResult:
    return SufficiencyResult(sufficiency=cls, reason="test")


def _grounding(ratio: float, unsupported: int = 0) -> GroundingResult:
    claims = [Claim(text="c", verdict=ClaimVerdict.SUPPORTED)]
    for _ in range(unsupported):
        claims.append(Claim(text="u", verdict=ClaimVerdict.UNSUPPORTED))
    return GroundingResult(
        claim_grounding=ratio, claims=claims, supported=1, unsupported=unsupported,
        contradicted=0, not_applicable=0,
    )


PROFILE = ThresholdProfile(name="test")


def test_insufficient_evidence_triggers_abstain() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.INSUFFICIENT), _grounding(1.0), 1.0, RiskTier.LOW, PROFILE)
    assert outcome.decision == GateDecision.ABSTAIN
    assert outcome.rule_fired == "insufficient_evidence"


def test_conflicting_high_risk_routes_to_human_review() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.CONFLICTING), _grounding(1.0), 1.0, RiskTier.HIGH, PROFILE)
    assert outcome.decision == GateDecision.HUMAN_REVIEW


def test_conflicting_low_risk_routes_to_qualified_answer() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.CONFLICTING), _grounding(1.0), 1.0, RiskTier.MEDIUM, PROFILE)
    assert outcome.decision == GateDecision.QUALIFIED_ANSWER


def test_high_risk_below_grounding_bar_routes_to_human_review() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(0.96), 1.0, RiskTier.HIGH, PROFILE)
    assert outcome.decision == GateDecision.HUMAN_REVIEW
    assert outcome.rule_fired == "high_risk_review"


def test_high_risk_low_faithfulness_routes_to_human_review() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(1.0), 0.90, RiskTier.HIGH, PROFILE)
    assert outcome.decision == GateDecision.HUMAN_REVIEW


def test_unsupported_claim_triggers_block() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(0.5, unsupported=1), 1.0, RiskTier.LOW, PROFILE)
    assert outcome.decision == GateDecision.BLOCK
    assert outcome.rule_fired == "grounding_block"


def test_grounding_below_threshold_triggers_block() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(0.80), 1.0, RiskTier.MEDIUM, PROFILE)
    assert outcome.decision == GateDecision.BLOCK


def test_partial_evidence_routes_to_qualified_answer() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.PARTIAL), _grounding(1.0), 1.0, RiskTier.MEDIUM, PROFILE)
    assert outcome.decision == GateDecision.QUALIFIED_ANSWER
    assert outcome.rule_fired == "partial_evidence"


def test_clean_case_answers() -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(1.0), 1.0, RiskTier.HIGH, PROFILE)
    assert outcome.decision == GateDecision.ANSWER


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (ThresholdProfile(name="strict", claim_grounding=0.98, high_risk_grounding=1.00), GateDecision.HUMAN_REVIEW),
        (ThresholdProfile(name="exploratory", claim_grounding=0.80, high_risk_grounding=0.90), GateDecision.ANSWER),
    ],
)
def test_profiles_change_the_bar(profile: ThresholdProfile, expected: GateDecision) -> None:
    outcome = apply_gate(_suff(SufficiencyClass.SUFFICIENT), _grounding(0.95), 1.0, RiskTier.HIGH, profile)
    assert outcome.decision == expected
