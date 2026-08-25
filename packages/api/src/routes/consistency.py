# This project was developed with assistance from AI tools.
"""Deterministic cross-document consistency endpoint."""

from db import get_db
from db.enums import UserRole
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import CurrentUser, require_roles
from ..schemas.consistency import ConsistencyCheckResponse
from ..services.consistency import run_consistency_check

router = APIRouter()

_REVIEW_ROLES = (UserRole.ADMIN, UserRole.LOAN_OFFICER, UserRole.UNDERWRITER)


@router.post(
    "/{application_id}/consistency-check",
    response_model=ConsistencyCheckResponse,
    dependencies=[Depends(require_roles(*_REVIEW_ROLES))],
)
async def check_application_consistency(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ConsistencyCheckResponse:
    """Run name and monthly-income rules without delegating decisions to an LLM."""
    result = await run_consistency_check(session, user, application_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return result
