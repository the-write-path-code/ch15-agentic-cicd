"""Layer 5: the deterministic policy gate (Chapter 4 rule cascade).

Single responsibility: turn sufficiency, grounding, and faithfulness into a
GateDecision using the fixed cascade. Constraints: the cascade order is a
book fact and must not change: INSUFFICIENT -> ABSTAIN; CONFLICTING ->
HUMAN_REVIEW (high risk) or QUALIFIED_ANSWER; high risk below
high_risk_grounding/high_risk_faithfulness -> HUMAN_REVIEW; grounding below
claim_grounding or any UNSUPPORTED claim -> BLOCK; PARTIAL ->
QUALIFIED_ANSWER; otherwise ANSWER.
"""
from __future__ import annotations

from day2ops.config import ThresholdProfile
from day2ops.schemas import (
    ClaimVerdict,
    GateDecision,
    GateOutcome,
    GroundingResult,
    RiskTier,
    SufficiencyClass,
    SufficiencyResult,
)


def apply_gate(
    sufficiency: SufficiencyResult,
    grounding: GroundingResult,
    faithfulness: float,
    risk_tier: RiskTier,
    profile: ThresholdProfile,
) -> GateOutcome:
    if sufficiency.sufficiency == SufficiencyClass.INSUFFICIENT:
        return GateOutcome(
            decision=GateDecision.ABSTAIN, reason=sufficiency.reason, rule_fired="insufficient_evidence"
        )
    if sufficiency.sufficiency == SufficiencyClass.CONFLICTING:
        if risk_tier == RiskTier.HIGH:
            return GateOutcome(
                decision=GateDecision.HUMAN_REVIEW,
                reason=sufficiency.reason,
                rule_fired="conflicting_evidence_high_risk",
            )
        return GateOutcome(
            decision=GateDecision.QUALIFIED_ANSWER,
            reason=sufficiency.reason,
            rule_fired="conflicting_evidence",
        )
    if risk_tier == RiskTier.HIGH and (
        grounding.claim_grounding < profile.high_risk_grounding
        or faithfulness < profile.high_risk_faithfulness
    ):
        return GateOutcome(
            decision=GateDecision.HUMAN_REVIEW,
            reason=(
                f"high risk case below bar: claim_grounding={grounding.claim_grounding:.3f}, "
                f"faithfulness={faithfulness:.3f}"
            ),
            rule_fired="high_risk_review",
        )
    has_unsupported = any(c.verdict == ClaimVerdict.UNSUPPORTED for c in grounding.claims)
    if grounding.claim_grounding < profile.claim_grounding or has_unsupported:
        return GateOutcome(
            decision=GateDecision.BLOCK,
            reason=(
                f"claim grounding {grounding.claim_grounding:.3f} below "
                f"{profile.claim_grounding} or unsupported claim present"
            ),
            rule_fired="grounding_block",
        )
    if sufficiency.sufficiency == SufficiencyClass.PARTIAL:
        return GateOutcome(
            decision=GateDecision.QUALIFIED_ANSWER, reason=sufficiency.reason, rule_fired="partial_evidence"
        )
    return GateOutcome(decision=GateDecision.ANSWER, reason="all gates passed", rule_fired="default_answer")
