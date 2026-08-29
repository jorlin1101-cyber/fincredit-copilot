# This project was developed with assistance from AI tools.
"""Underwriting REST endpoints for risk assessment and compliance results."""

from db import get_db
from db.enums import UserRole
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import CurrentUser, require_roles
from ..schemas.compliance_result import ComplianceResultResponse
from ..schemas.deterministic_assessment import (
    DeterministicAssessmentRequest,
    DeterministicAssessmentResponse,
)
from ..schemas.risk_assessment import RiskAssessmentResponse
from ..services.compliance_result import get_latest_compliance_result
from ..services.deterministic_assessment import run_deterministic_assessment
from ..services.risk_assessment import get_latest_risk_assessment

router = APIRouter()

_UW_ROLES = [
    UserRole.ADMIN,
    UserRole.UNDERWRITER,
    UserRole.LOAN_OFFICER,
    UserRole.CEO,
]


@router.post(
    "/{application_id}/deterministic-assessment",
    response_model=DeterministicAssessmentResponse,
    dependencies=[
        Depends(require_roles(UserRole.ADMIN, UserRole.UNDERWRITER, UserRole.LOAN_OFFICER))
    ],
)
async def create_deterministic_assessment(
    application_id: int,
    payload: DeterministicAssessmentRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DeterministicAssessmentResponse:
    """Calculate DTI/LTV and evidence gates without delegating arithmetic to an LLM."""
    trace_id = request.headers.get("x-request-id") or request.headers.get("x-trace-id")
    if not trace_id:
        import uuid

        trace_id = str(uuid.uuid4())
    result = await run_deterministic_assessment(
        session,
        user,
        application_id,
        proposed_monthly_payment=payload.proposed_monthly_payment,
        trace_id=trace_id,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到贷款申请")
    return result


@router.get(
    "/{application_id}/risk-assessment",
    response_model=RiskAssessmentResponse,
    dependencies=[Depends(require_roles(*_UW_ROLES))],
)
async def get_risk_assessment(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> RiskAssessmentResponse:
    """Get the latest risk assessment for an application.

    Returns 404 if no risk assessment has been run yet.
    """
    record = await get_latest_risk_assessment(session, application_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk assessment found for this application",
        )
    return RiskAssessmentResponse.model_validate(record)


@router.get(
    "/{application_id}/compliance-result",
    response_model=ComplianceResultResponse,
    dependencies=[Depends(require_roles(*_UW_ROLES))],
)
async def get_compliance_result(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ComplianceResultResponse:
    """Get the latest compliance check result for an application.

    Returns 404 if no compliance check has been run yet.
    """
    record = await get_latest_compliance_result(session, application_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance result found for this application",
        )
    return ComplianceResultResponse.model_validate(record)
