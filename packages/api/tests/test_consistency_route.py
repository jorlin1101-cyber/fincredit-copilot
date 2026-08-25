# This project was developed with assistance from AI tools.
"""API tests for deterministic consistency checks."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from db import get_db
from db.enums import UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.consistency import router
from src.schemas.auth import DataScope, UserContext
from src.schemas.consistency import ConsistencyCheckResponse


def _app(role: UserRole):
    app = FastAPI()
    app.include_router(router, prefix="/api/applications")
    user = UserContext(
        user_id="route-user",
        role=role,
        email="route@example.test",
        name="路由测试",
        data_scope=DataScope(full_pipeline=True),
    )

    async def fake_user():
        return user

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db
    return app


def test_loan_officer_can_run_consistency_check():
    result = ConsistencyCheckResponse(
        application_id=99,
        status="passed",
        checked_at=datetime.now(UTC),
        checks_performed=["name", "monthly_income"],
        issues=[],
        warnings=[],
        rule_versions={
            "name": "name-exact-v1",
            "monthly_income": "income-relative-v1",
        },
    )
    with patch(
        "src.routes.consistency.run_consistency_check",
        new_callable=AsyncMock,
        return_value=result,
    ):
        response = TestClient(_app(UserRole.LOAN_OFFICER)).post(
            "/api/applications/99/consistency-check"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert response.json()["rule_versions"]["name"] == "name-exact-v1"


def test_borrower_cannot_run_internal_consistency_check():
    response = TestClient(_app(UserRole.BORROWER)).post("/api/applications/99/consistency-check")
    assert response.status_code == 403
