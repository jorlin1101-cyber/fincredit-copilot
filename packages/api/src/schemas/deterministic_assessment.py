# This project was developed with assistance from AI tools.
"""Schemas for deterministic DTI/LTV and human-review assessment."""

from datetime import datetime

from pydantic import BaseModel, Field


class DeterministicAssessmentRequest(BaseModel):
    proposed_monthly_payment: float = Field(default=0, ge=0, le=10_000_000)


class RiskMetric(BaseModel):
    value: float | None
    rating: str | None
    formula: str
    inputs: dict[str, float]
    rule_version: str


class DocumentGate(BaseModel):
    required: list[str]
    provided: list[str]
    missing: list[str]
    pending_human_review: list[str]
    is_complete: bool


class DeterministicAssessmentResponse(BaseModel):
    id: int | None = None
    application_id: int
    trace_id: str
    calculated_at: datetime
    dti: RiskMetric
    ltv: RiskMetric
    documents: DocumentGate
    consistency_status: str
    consistency_issue_count: int
    suggestion: str
    rationale: list[str]
    human_review_required: bool = True
    confirmation_instruction: str
    rule_versions: dict[str, str]
