# This project was developed with assistance from AI tools.
"""Validated schemas for the three Chinese P0 lending documents."""

from typing import Literal

from db.enums import ExtractionMethod
from pydantic import BaseModel, ConfigDict, Field


class EvidenceField(BaseModel):
    """A source-grounded value produced by document extraction."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    normalized_value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: int = Field(ge=1)
    evidence_text: str = Field(min_length=1, max_length=500)
    extraction_method: ExtractionMethod


class BankTransaction(BaseModel):
    """A salary-related transaction retained for income consistency checks."""

    model_config = ConfigDict(extra="forbid")

    transaction_date: EvidenceField
    counterparty: EvidenceField | None = None
    summary: EvidenceField | None = None
    amount: EvidenceField


class IdentityCardSchema(BaseModel):
    """Chinese resident identity card fields used by the lending workflow."""

    model_config = ConfigDict(extra="forbid")

    document_type: Literal["id_card"] = "id_card"
    full_name: EvidenceField | None = None
    id_number: EvidenceField | None = None
    date_of_birth: EvidenceField | None = None
    address: EvidenceField | None = None
    issuing_authority: EvidenceField | None = None
    valid_from: EvidenceField | None = None
    valid_until: EvidenceField | None = None


class IncomeCertificateSchema(BaseModel):
    """Employer-issued income certificate fields."""

    model_config = ConfigDict(extra="forbid")

    document_type: Literal["income_certificate"] = "income_certificate"
    employee_name: EvidenceField | None = None
    employer_name: EvidenceField | None = None
    employer_unified_credit_code: EvidenceField | None = None
    position: EvidenceField | None = None
    employment_start_date: EvidenceField | None = None
    monthly_gross_income: EvidenceField | None = None
    annual_gross_income: EvidenceField | None = None
    issue_date: EvidenceField | None = None
    contact_phone: EvidenceField | None = None


class BankStatementSchema(BaseModel):
    """Bank statement summary and salary credits used by P0 checks."""

    model_config = ConfigDict(extra="forbid")

    document_type: Literal["bank_statement"] = "bank_statement"
    account_holder_name: EvidenceField | None = None
    bank_name: EvidenceField | None = None
    account_number_last4: EvidenceField | None = None
    statement_period_start: EvidenceField | None = None
    statement_period_end: EvidenceField | None = None
    opening_balance: EvidenceField | None = None
    ending_balance: EvidenceField | None = None
    salary_credit_total: EvidenceField | None = None
    salary_credit_monthly_average: EvidenceField | None = None
    salary_credits: list[BankTransaction] = Field(default_factory=list)


ChineseDocumentSchema = IdentityCardSchema | IncomeCertificateSchema | BankStatementSchema
