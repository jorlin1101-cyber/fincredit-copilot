# This project was developed with assistance from AI tools.
"""Policy provenance and version metadata schemas."""

from datetime import date

from db.enums import PolicyJurisdiction, PolicySourceType
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyMetadata(BaseModel):
    """Metadata required to make a policy citation independently verifiable."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    issuer: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)
    jurisdiction: PolicyJurisdiction
    source_type: PolicySourceType
    version: str | None = Field(default=None, max_length=100)
    published_date: date | None = None
    effective_date: date | None = None
    expires_at: date | None = None
    retrieved_date: date
    description: str | None = None

    @model_validator(mode="after")
    def validate_provenance_and_dates(self) -> "PolicyMetadata":
        if self.source_type in {
            PolicySourceType.OFFICIAL,
            PolicySourceType.PUBLIC_REPORT,
        } and not self.source_url:
            raise ValueError("verifiable policy metadata requires source_url")
        if self.effective_date and self.expires_at and self.expires_at < self.effective_date:
            raise ValueError("expires_at must not be earlier than effective_date")
        if self.published_date and self.retrieved_date < self.published_date:
            raise ValueError("retrieved_date must not be earlier than published_date")
        if (
            self.source_type == PolicySourceType.INTERNAL_DEMO
            and self.jurisdiction != PolicyJurisdiction.INTERNAL_DEMO
        ):
            raise ValueError("internal demo policies must use internal_demo jurisdiction")
        return self
