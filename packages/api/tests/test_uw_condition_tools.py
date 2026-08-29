# This project was developed with assistance from AI tools.
"""Unit tests for underwriter condition lifecycle LangGraph tools.

Mocked DB pattern matching test_compliance_check_tool.py -- verifies tool
behavior for each condition lifecycle operation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.condition_tools import (
    uw_clear_condition,
    uw_condition_summary,
    uw_issue_condition,
    uw_return_condition,
    uw_review_condition,
    uw_waive_condition,
)


def _state(user_id="uw-maria", role="underwriter"):
    return {"user_id": user_id, "user_role": role}


def _mock_session():
    session = AsyncMock()
    return session


def _patch_session():
    """Patch SessionLocal to return a mock async context manager."""
    mock_session_cls = patch("src.agents.condition_tools.SessionLocal")
    return mock_session_cls


# ---------------------------------------------------------------------------
# uw_issue_condition
# ---------------------------------------------------------------------------


class TestUwIssueCondition:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.issue_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_happy_path(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 42,
            "description": "Provide updated pay stubs",
            "severity": "prior_to_docs",
            "status": "open",
            "due_date": None,
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_issue_condition.ainvoke(
            {
                "application_id": 100,
                "description": "Provide updated pay stubs",
                "severity": "prior_to_docs",
                "state": _state(),
            }
        )
        assert "审批条件 #42" in result
        assert "合同文件生成前完成" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.issue_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_service):
        mock_service.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_issue_condition.ainvoke(
            {
                "application_id": 999,
                "description": "Pay stubs",
                "state": _state(),
            }
        )
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_invalid_severity(self):
        result = await uw_issue_condition.ainvoke(
            {
                "application_id": 100,
                "description": "Pay stubs",
                "severity": "invalid_level",
                "state": _state(),
            }
        )
        assert "无法识别完成节点" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.issue_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_with_due_date(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 43,
            "description": "Bank statements",
            "severity": "prior_to_closing",
            "status": "open",
            "due_date": "2026-03-15T00:00:00+00:00",
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_issue_condition.ainvoke(
            {
                "application_id": 100,
                "description": "Bank statements",
                "severity": "prior_to_closing",
                "due_date": "2026-03-15",
                "state": _state(),
            }
        )
        assert "审批条件 #43" in result
        assert "2026-03-15" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.issue_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_default_severity(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 44,
            "description": "W2 forms",
            "severity": "prior_to_docs",
            "status": "open",
            "due_date": None,
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_issue_condition.ainvoke(
            {
                "application_id": 100,
                "description": "W2 forms",
                "state": _state(),
            }
        )
        assert "合同文件生成前完成" in result
        # Verify the service was called with PRIOR_TO_DOCS
        from db.enums import ConditionSeverity

        call_args = mock_service.call_args
        assert call_args[0][4] == ConditionSeverity.PRIOR_TO_DOCS


# ---------------------------------------------------------------------------
# uw_review_condition
# ---------------------------------------------------------------------------


class TestUwReviewCondition:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.review_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_happy_path(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 5,
            "description": "Verify employment",
            "status": "under_review",
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_review_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "state": _state(),
            }
        )
        assert "已转入复核" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.review_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_service):
        mock_service.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_review_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 999,
                "state": _state(),
            }
        )
        assert "未找到" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.review_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_wrong_status(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "error": "审批条件 #5 当前状态为“待处理”，只有“已响应”的条件可以转入复核。"
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_review_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "state": _state(),
            }
        )
        assert "已响应" in result


# ---------------------------------------------------------------------------
# uw_clear_condition
# ---------------------------------------------------------------------------


class TestUwClearCondition:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.get_condition_summary", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.clear_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_happy_path(self, mock_session_cls, mock_clear, mock_summary):
        mock_clear.return_value = {
            "id": 5,
            "description": "Verify employment",
            "status": "cleared",
            "cleared_by": "uw-maria",
        }
        mock_summary.return_value = {
            "total": 3,
            "counts": {
                "open": 1,
                "responded": 0,
                "under_review": 0,
                "cleared": 2,
                "waived": 0,
                "escalated": 0,
            },
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_clear_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "state": _state(),
            }
        )
        assert "审批条件 #5 已标记为完成" in result
        assert "当前剩余" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.clear_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_clear):
        mock_clear.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_clear_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 999,
                "state": _state(),
            }
        )
        assert "未找到" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.clear_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_wrong_status(self, mock_session_cls, mock_clear):
        mock_clear.return_value = {
            "error": "审批条件 #5 当前状态为“待处理”，只有“已响应”或“复核中”的条件可以标记为完成。"
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_clear_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "state": _state(),
            }
        )
        assert "已响应" in result


# ---------------------------------------------------------------------------
# uw_waive_condition
# ---------------------------------------------------------------------------


class TestUwWaiveCondition:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.waive_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_happy_path(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 7,
            "description": "Title insurance",
            "status": "waived",
            "waiver_rationale": "Seller providing title insurance",
            "cleared_by": "uw-maria",
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_waive_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 7,
                "rationale": "Seller providing title insurance",
                "state": _state(),
            }
        )
        assert "审批条件 #7 已由有权人员豁免" in result
        assert "Seller providing title insurance" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.waive_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_service):
        mock_service.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_waive_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 999,
                "rationale": "Not needed",
                "state": _state(),
            }
        )
        assert "未找到" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.waive_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_blocked_severity(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "error": "审批条件 #5 的完成节点为“审批前完成”，仅“签约前完成”或“放款前完成”的条件可由有权人员豁免。"
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_waive_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "rationale": "Not needed",
                "state": _state(),
            }
        )
        assert "签约前完成" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.waive_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_rationale_in_output(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 8,
            "description": "Flood cert",
            "status": "waived",
            "waiver_rationale": "Property not in flood zone per FEMA map",
            "cleared_by": "uw-maria",
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_waive_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 8,
                "rationale": "Property not in flood zone per FEMA map",
                "state": _state(),
            }
        )
        assert "Property not in flood zone" in result


# ---------------------------------------------------------------------------
# uw_return_condition
# ---------------------------------------------------------------------------


class TestUwReturnCondition:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.return_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_happy_path(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "id": 5,
            "description": "Verify employment",
            "status": "open",
            "iteration_count": 2,
            "response_text": "Original\n[Return #2]: Missing page 2",
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_return_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "note": "Missing page 2",
                "state": _state(),
            }
        )
        assert "退回补充" in result
        assert "第 2 次" in result
        assert "Missing page 2" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.return_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_service):
        mock_service.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_return_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 999,
                "note": "Incomplete",
                "state": _state(),
            }
        )
        assert "未找到" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.return_condition", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_wrong_status(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "error": "审批条件 #5 当前状态为“待处理”，只有“复核中”的条件可以退回补充。"
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_return_condition.ainvoke(
            {
                "application_id": 100,
                "condition_id": 5,
                "note": "Incomplete",
                "state": _state(),
            }
        )
        assert "复核中" in result


# ---------------------------------------------------------------------------
# uw_condition_summary
# ---------------------------------------------------------------------------


class TestUwConditionSummary:
    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.get_condition_summary", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_counts(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "total": 5,
            "counts": {
                "open": 2,
                "responded": 1,
                "under_review": 0,
                "cleared": 1,
                "waived": 1,
                "escalated": 0,
            },
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_condition_summary.ainvoke(
            {
                "application_id": 100,
                "state": _state(),
            }
        )
        assert "共 5 项" in result
        assert "待处理：2 项" in result
        assert "已解决：2 项" in result
        assert "未解决：3 项" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.get_condition_summary", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_empty(self, mock_session_cls, mock_service):
        mock_service.return_value = {
            "total": 0,
            "counts": {
                "open": 0,
                "responded": 0,
                "under_review": 0,
                "cleared": 0,
                "waived": 0,
                "escalated": 0,
            },
        }
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_condition_summary.ainvoke(
            {
                "application_id": 100,
                "state": _state(),
            }
        )
        assert "没有审批条件" in result

    @pytest.mark.asyncio
    @patch("src.agents.condition_tools.get_condition_summary", new_callable=AsyncMock)
    @patch("src.agents.condition_tools.SessionLocal")
    async def test_not_found(self, mock_session_cls, mock_service):
        mock_service.return_value = None
        session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await uw_condition_summary.ainvoke(
            {
                "application_id": 999,
                "state": _state(),
            }
        )
        assert "未找到" in result
