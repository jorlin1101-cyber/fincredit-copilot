# This project was developed with assistance from AI tools.
"""Cross-document consistency evidence schemas."""

from datetime import datetime
from typing import Literal

from db.enums import DocumentType
from pydantic import BaseModel, ConfigDict, Field


class ConsistencyEvidence(BaseModel):
    """A value and its independently reviewable origin."""

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["application", "document"]
    document_id: int | None = None
    document_type: DocumentType | None = None
    field_name: str
    value: str
    normalized_value: str
    source_page: int | None = None
    evidence_text: str | None = None


class ConsistencyIssue(BaseModel):
    """A deterministic conflict. No model decides whether it exists."""

    model_config = ConfigDict(extra="forbid")

    issue_type: Literal["name_mismatch", "income_mismatch"]
    field_name: Literal["name", "monthly_income"]
    left: ConsistencyEvidence
    right: ConsistencyEvidence
    difference_ratio: float | None = Field(default=None, ge=0.0)
    threshold: float = Field(ge=0.0)
    rule_version: str
    recommendation: str


class ConsistencyCheckResponse(BaseModel):
    """Result of all P0 deterministic consistency rules."""

    application_id: int
    status: Literal["passed", "issues_found", "insufficient_data"]
    checked_at: datetime
    checks_performed: list[Literal["name", "monthly_income"]]
    issues: list[ConsistencyIssue]
    warnings: list[str]
    rule_versions: dict[str, str]
