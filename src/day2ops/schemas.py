"""Typed schemas for every structure that crosses a module boundary.

Single responsibility: define the pydantic models and enums shared by the
evaluation, migration, telemetry, red-team, and HITL modules. Constraints:
no runtime behavior beyond validation and small derived properties; names and
values follow the book (ClaimVerdict, SufficiencyClass, RagasMetrics style).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SufficiencyClass(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"


class GateDecision(str, Enum):
    ANSWER = "ANSWER"
    QUALIFIED_ANSWER = "QUALIFIED_ANSWER"
    ABSTAIN = "ABSTAIN"
    BLOCK = "BLOCK"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CaseStatus(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    PRODUCTION_FROZEN = "PRODUCTION-FROZEN"


class PromptPersona(str, Enum):
    FAITHFUL = "faithful"
    FABRICATING = "fabricating"


class EvaluationMode(str, Enum):
    REPLAY = "replay"
    MOCK = "mock"
    LIVE = "live"


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    classification: str = "internal"
    superseded: bool = False
    contains_adversarial_payload: bool = False
    department_scope: str = "all"


class PolicyDocument(BaseModel):
    doc_id: str
    title: str
    classification: str
    department_scope: str
    effective_date: str
    superseded_by: str | None = None
    contains_adversarial_payload: bool = False
    chunks: list[Chunk] = Field(default_factory=list)


class GoldenCase(BaseModel):
    case_id: str
    question: str
    risk_tier: RiskTier
    expected_answer: str
    expected_doc_ids: list[str] = Field(default_factory=list)
    should_answer: bool = True
    failure_mode_tag: str = "none"
    status: CaseStatus = CaseStatus.PROVISIONAL
    origin: str = "authored"
    added_at: str = "2026-08-30"
    added_by: str = "author"


class RetrievedChunk(BaseModel):
    chunk_id: str
    score: float


class Claim(BaseModel):
    text: str
    verdict: ClaimVerdict
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class GroundingResult(BaseModel):
    claim_grounding: float
    claims: list[Claim]
    supported: int
    unsupported: int
    contradicted: int
    not_applicable: int


class SufficiencyResult(BaseModel):
    sufficiency: SufficiencyClass
    reason: str
    relevant_chunk_ids: list[str] = Field(default_factory=list)


class RagasMetrics(BaseModel):
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevance: float


class RetrievalMetrics(BaseModel):
    recall_at_5: float
    precision_at_5: float
    mrr: float


class GateOutcome(BaseModel):
    decision: GateDecision
    reason: str
    rule_fired: str


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)


class TraceRecord(BaseModel):
    case_id: str
    question: str
    prompt_version: str
    persona: PromptPersona
    retrieved: list[RetrievedChunk]
    answer: str
    citations: list[str] = Field(default_factory=list)
    sufficiency: SufficiencyClass
    metrics: dict[str, float] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    gate_decision: GateDecision
    gate_reason: str = ""
    risk_tier: RiskTier
    status: CaseStatus
    token_usage: TokenUsage
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LayerResult(BaseModel):
    passed: bool
    layer_name: str
    reason: str
    metadata: dict[str, object] = Field(default_factory=dict)


class AdversarialCase(BaseModel):
    case_id: str
    category: str
    payload: str
    delivery: str
    expected_blocked_layer: int | None = None
    expected_reason_pattern: str | None = None
    must_fail_closed: bool = False
    control_case_id: str | None = None
    control_case: bool = False
    user_role: str = "public"
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class OverrideRecord(BaseModel):
    override_id: str
    question: str
    original_output: dict[str, object]
    corrected_output: str
    rationale: str
    reviewer: str
    timestamp: str
    disposition: str
    risk_tier: RiskTier = RiskTier.MEDIUM
    security_block: bool = False
    expected_doc_ids: list[str] = Field(default_factory=list)
    blocked_layer: int | None = None


class AuditEntry(BaseModel):
    case_id: str
    from_status: str
    to_status: str
    reviewer: str
    evidence: str
    timestamp: str


class DriftAlert(BaseModel):
    window: str
    value: float
    reason: str


class SignatureDiff(BaseModel):
    tool: str
    added_params: list[str]
    removed_params: list[str]
    changed_params: list[str]
    breaking: bool
    details: str
