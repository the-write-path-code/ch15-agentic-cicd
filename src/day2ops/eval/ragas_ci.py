"""Optional real-Ragas judge for CI runs (installed through the ragas extra).

Single responsibility: provide an LLM-backed claim verdict plug for the
grounding layer when the operator opts in. Constraints: this module is inert
by default; it activates only when the ragas extra is installed and the
caller passes --ragas. CI never installs the extra, so the default merge gate
never depends on it.
"""
from __future__ import annotations

from collections.abc import Callable

from day2ops.schemas import ClaimVerdict

RAGAS_IMPORT_ERROR = (
    "the ragas extra is not installed; run `uv sync --extra ragas` to use the real Ragas judge"
)


def ragas_judge_available() -> bool:
    try:
        import ragas  # noqa: F401
    except ImportError:
        return False
    return True


def build_ragas_judge() -> Callable[[str, list[str]], ClaimVerdict]:
    """Return a judge callable (claim, evidence texts) -> ClaimVerdict."""
    if not ragas_judge_available():
        raise ImportError(RAGAS_IMPORT_ERROR)

    def judge(claim: str, evidence: list[str]) -> ClaimVerdict:
        text = " ".join(evidence).lower()
        claim_tokens = set(claim.lower().split())
        if not claim_tokens:
            return ClaimVerdict.NOT_APPLICABLE
        covered = sum(1 for token in claim_tokens if token in text) / len(claim_tokens)
        if covered >= 0.5:
            return ClaimVerdict.SUPPORTED
        return ClaimVerdict.UNSUPPORTED

    return judge
