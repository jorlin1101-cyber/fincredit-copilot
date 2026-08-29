# This project was developed with assistance from AI tools.
"""Tests for chat authentication, application context, and route factory.

Validates that WebSocket chat routes are created correctly and that the
ConversationHistoryResponse schema works as expected.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import ApplicationStage, UserRole
from fastapi import APIRouter

from src.routes._chat_handler import (
    _build_application_context,
    create_authenticated_chat_router,
)
from src.schemas.auth import DataScope, UserContext
from src.schemas.conversation import ConversationHistoryResponse


def _user(role: UserRole) -> UserContext:
    user_id = "loan-officer-001" if role == UserRole.LOAN_OFFICER else "borrower-001"
    scope = (
        DataScope(assigned_to=user_id)
        if role == UserRole.LOAN_OFFICER
        else DataScope(own_data_only=True, user_id=user_id)
    )
    return UserContext(
        user_id=user_id,
        role=role,
        email=f"{user_id}@example.com",
        name="测试用户",
        data_scope=scope,
    )


def _session_factory() -> MagicMock:
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    context.__aexit__.return_value = False
    return MagicMock(return_value=context)


def test_chat_route_factory_creates_router():
    """create_authenticated_chat_router returns an APIRouter."""
    router = create_authenticated_chat_router(
        role=UserRole.BORROWER,
        agent_name="borrower-assistant",
        ws_path="/borrower/chat",
        history_path="/borrower/conversations/history",
    )
    assert isinstance(router, APIRouter)


def test_conversation_history_response_schema():
    """ConversationHistoryResponse validates correctly."""
    response = ConversationHistoryResponse(
        data=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    )
    assert len(response.data) == 2
    assert response.data[0].role == "user"
    assert response.data[0].content == "Hello"
    assert response.data[1].role == "assistant"
    assert response.data[1].content == "Hi there!"


def test_conversation_history_response_empty():
    """ConversationHistoryResponse accepts empty message list."""
    response = ConversationHistoryResponse(data=[])
    assert len(response.data) == 0


@pytest.mark.asyncio
async def test_loan_officer_application_context_uses_current_page_application():
    """The LO assistant must answer about the application open on the current page."""
    application = SimpleNamespace(
        id=353,
        stage=ApplicationStage.CLOSED,
        loan_amount=Decimal("2000000"),
        property_address="成都市高新区天府一街演示公寓1栋",
    )

    with (
        patch("db.database.SessionLocal", _session_factory()),
        patch(
            "src.services.application.get_application",
            new=AsyncMock(return_value=application),
        ) as get_application,
    ):
        result = await _build_application_context(
            _user(UserRole.LOAN_OFFICER), application_id=353
        )

    assert "申请编号为#353" in result
    assert "阶段为已结案" in result
    assert "人民币2,000,000元" in result
    assert "不要向用户询问申请编号" in result
    get_application.assert_awaited_once()


@pytest.mark.asyncio
async def test_borrower_application_context_selects_most_advanced_application():
    """Without a page ID, borrower chat should use the furthest progressed application."""
    applications = [
        SimpleNamespace(
            id=101,
            stage=ApplicationStage.APPLICATION,
            loan_amount=Decimal("800000"),
            property_address="成都市武侯区演示路1号",
        ),
        SimpleNamespace(
            id=102,
            stage=ApplicationStage.CONDITIONAL_APPROVAL,
            loan_amount=Decimal("1200000"),
            property_address="成都市锦江区演示路2号",
        ),
    ]

    with (
        patch("db.database.SessionLocal", _session_factory()),
        patch(
            "src.services.application.list_applications",
            new=AsyncMock(return_value=(applications, len(applications))),
        ),
    ):
        result = await _build_application_context(_user(UserRole.BORROWER))

    assert "申请编号为#102" in result
    assert "阶段为有条件通过" in result
