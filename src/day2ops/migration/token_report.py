"""Token usage aggregation for migration runs (Chapter 15.2).

Single responsibility: aggregate token usage from traces, report totals and
the per-case p95, and compare against the generator's rate limits from
models.yaml. Constraints: pure computation over recorded traces.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from day2ops.schemas import TraceRecord


class TokenReport(BaseModel):
    case_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    per_case_p95: int
    per_case_max: int
    warnings: list[str] = Field(default_factory=list)


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    index = min(len(sorted_values) - 1, int(round(pct / 100.0 * (len(sorted_values) - 1))))
    return sorted_values[index]


def build_token_report(
    traces: list[TraceRecord], tokens_per_minute: int
) -> TokenReport:
    totals = [t.token_usage.total_tokens for t in traces]
    sorted_totals = sorted(totals)
    prompt = sum(t.token_usage.prompt_tokens for t in traces)
    completion = sum(t.token_usage.completion_tokens for t in traces)
    warnings: list[str] = []
    p95 = _percentile(sorted_totals, 95)
    if p95 > tokens_per_minute:
        warnings.append(
            f"per-case p95 token usage ({p95}) exceeds the generator's "
            f"tokens_per_minute budget ({tokens_per_minute})"
        )
    case_max = max(totals) if totals else 0
    if case_max > tokens_per_minute:
        warnings.append(f"single case used {case_max} tokens, above the per-minute budget")
    return TokenReport(
        case_count=len(traces),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        per_case_p95=p95,
        per_case_max=case_max,
        warnings=warnings,
    )
