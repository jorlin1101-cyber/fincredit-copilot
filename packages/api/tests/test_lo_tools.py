# This project was developed with assistance from AI tools.
"""Unit tests for loan officer agent tools.

Focus: _user_context_from_state (affects all tools), one representative
read tool, and the two write tools with real logic (mark resubmission,
submit to underwriting).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import ApplicationStage, UserRole

from src.agents.loan_officer_tools import (
    _user_context_from_state,
    lo_application_detail,
    lo_draft_communication,
    lo_mark_resubmission,
    lo_send_communication,
    lo_submit_to_underwriting,
)

# ---------------------------------------------------------------------------
# _user_context_from_state
# ---------------------------------------------------------------------------


class TestUserContextFromState:
    """The helper that builds UserContext for all LO tools."""

    def test_builds_lo_scope(self):
        """loan_officer role produces DataScope(assigned_to=user_id)."""
        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
            "user_email": "james@example.com",
            "user_name": "James Torres",
        }
        ctx = _user_context_from_state(state)

        assert ctx.user_id == "lo-james"
        assert ctx.role == UserRole.LOAN_OFFICER
        assert ctx.data_scope.assigned_to == "lo-james"
        assert ctx.data_scope.own_data_only is False
        assert ctx.data_scope.full_pipeline is False


# ---------------------------------------------------------------------------
# Representative read tool
# ---------------------------------------------------------------------------


class TestLoApplicationDetail:
    """Verify the read pattern: calls services and produces output."""

    @pytest.mark.asyncio
    async def test_calls_services_and_formats(self):
        """lo_application_detail calls get_application + get_application_status."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.APPLICATION
        mock_app.loan_type = MagicMock(value="conventional_30")
        mock_app.property_address = "成都市高新区天府一街演示公寓1栋"
        mock_app.loan_amount = 350000
        mock_app.property_value = 450000
        mock_app.application_borrowers = []

        mock_status = MagicMock()
        mock_status.provided_doc_count = 3
        mock_status.required_doc_count = 4
        mock_status.is_document_complete = False
        mock_status.open_condition_count = 0
        mock_status.pending_actions = []

        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
        }

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ) as mock_get_app,
            patch(
                "src.agents.loan_officer_tools.get_application_status",
                new_callable=AsyncMock,
                return_value=mock_status,
            ) as mock_get_status,
            patch(
                "src.agents.loan_officer_tools.SessionLocal",
            ) as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_application_detail.ainvoke({"application_id": 101, "state": state})

        assert "申请 #101" in result
        assert "申请中" in result
        assert "3/4" in result  # doc counts
        mock_get_app.assert_awaited_once()
        mock_get_status.assert_awaited_once()


# ---------------------------------------------------------------------------
# lo_mark_resubmission (write tool)
# ---------------------------------------------------------------------------


class TestLoMarkResubmission:
    """Write tool: update_document_status + write_audit_event."""

    @pytest.mark.asyncio
    async def test_writes_status_and_audit(self):
        """Marks doc for resubmission and writes audit event."""
        mock_doc = MagicMock()
        mock_doc.id = 10

        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
        }

        with (
            patch(
                "src.agents.loan_officer_tools.update_document_status",
                new_callable=AsyncMock,
                return_value=mock_doc,
            ) as mock_update,
            patch(
                "src.agents.loan_officer_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch(
                "src.agents.loan_officer_tools.SessionLocal",
            ) as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_mark_resubmission.ainvoke(
                {
                    "application_id": 101,
                    "document_id": 10,
                    "reason": "扫描件模糊",
                    "state": state,
                }
            )

        assert "需要重新提交" in result
        mock_update.assert_awaited_once()
        mock_audit.assert_awaited_once()
        # Verify audit event type
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "document_flagged_for_resubmission"


# ---------------------------------------------------------------------------
# lo_submit_to_underwriting (write tool)
# ---------------------------------------------------------------------------


class TestLoSubmitToUnderwriting:
    """The most important test -- double transition + dual audit."""

    @pytest.mark.asyncio
    async def test_happy_path_dual_transition(self):
        """Both transitions happen in order with audit events."""
        mock_app_processing = MagicMock()
        mock_app_processing.stage = ApplicationStage.PROCESSING

        mock_app_underwriting = MagicMock()
        mock_app_underwriting.stage = ApplicationStage.UNDERWRITING

        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
        }

        with (
            patch(
                "src.agents.loan_officer_tools.check_underwriting_readiness",
                new_callable=AsyncMock,
                return_value={"is_ready": True, "blockers": []},
            ),
            patch(
                "src.agents.loan_officer_tools.transition_stage",
                new_callable=AsyncMock,
                side_effect=[mock_app_processing, mock_app_underwriting],
            ) as mock_transition,
            patch(
                "src.agents.loan_officer_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch(
                "src.agents.loan_officer_tools.SessionLocal",
            ) as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_submit_to_underwriting.ainvoke(
                {"application_id": 101, "state": state}
            )

        assert "已提交授信审批" in result
        assert mock_transition.await_count == 2

        # Verify transition order
        calls = mock_transition.call_args_list
        assert calls[0].args[3] == ApplicationStage.PROCESSING
        assert calls[1].args[3] == ApplicationStage.UNDERWRITING

        # Two audit events
        assert mock_audit.await_count == 2

    @pytest.mark.asyncio
    async def test_blocked_when_not_ready(self):
        """Readiness gate blocks submission and returns blockers."""
        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
        }

        with (
            patch(
                "src.agents.loan_officer_tools.check_underwriting_readiness",
                new_callable=AsyncMock,
                return_value={
                    "is_ready": False,
                    "blockers": ["缺少必需材料：收入证明"],
                },
            ),
            patch(
                "src.agents.loan_officer_tools.transition_stage",
                new_callable=AsyncMock,
            ) as mock_transition,
            patch(
                "src.agents.loan_officer_tools.SessionLocal",
            ) as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_submit_to_underwriting.ainvoke(
                {"application_id": 101, "state": state}
            )

        assert "暂时无法提交授信审批" in result
        assert "收入证明" in result
        mock_transition.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_app_not_found(self):
        """Returns error message (not exception) when app is out of scope."""
        state = {
            "user_id": "lo-james",
            "user_role": "loan_officer",
        }

        with (
            patch(
                "src.agents.loan_officer_tools.check_underwriting_readiness",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.agents.loan_officer_tools.SessionLocal",
            ) as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_submit_to_underwriting.ainvoke(
                {"application_id": 999, "state": state}
            )

        assert "未找到" in result


# ---------------------------------------------------------------------------
# lo_draft_communication
# ---------------------------------------------------------------------------


class TestLoDraftCommunication:
    """Context-gathering tool for borrower communication drafts."""

    @pytest.mark.asyncio
    async def test_gathers_all_context_sections(self):
        """Mocks 4 services; output contains BORROWER, LOAN DETAILS, DOCUMENTS,
        CONDITIONS, RATE LOCK sections with correct data."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "晓雨"
        mock_borrower.last_name = "李"
        mock_borrower.email = "xiaoyu.li@example.com"

        mock_ab = MagicMock()
        mock_ab.is_primary = True
        mock_ab.borrower = mock_borrower

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.APPLICATION
        mock_app.loan_type = MagicMock(value="fha")
        mock_app.property_address = "成都市高新区天府三街演示家园8栋"
        mock_app.loan_amount = 425000
        mock_app.application_borrowers = [mock_ab]

        mock_completeness = MagicMock()
        mock_completeness.provided_count = 2
        mock_completeness.required_count = 4
        mock_req_provided = MagicMock()
        mock_req_provided.label = "收入证明"
        mock_req_provided.is_provided = True
        mock_req_provided.status = MagicMock(value="processing_complete")
        mock_req_provided.quality_flags = []
        mock_req_missing = MagicMock()
        mock_req_missing.label = "银行流水"
        mock_req_missing.is_provided = False
        mock_req_missing.status = None
        mock_req_missing.quality_flags = []
        mock_completeness.requirements = [mock_req_provided, mock_req_missing]

        mock_conditions = [
            {
                "id": 1,
                "description": "补充加盖单位公章的在职证明",
                "severity": "prior_to_approval",
                "status": "open",
            }
        ]

        mock_rate_lock = {
            "application_id": 101,
            "status": "active",
            "locked_rate": 3.1,
            "lock_date": "2026-08-01",
            "expiration_date": "2026-09-15",
            "days_remaining": 4,
            "is_urgent": True,
        }

        state = {"user_id": "lo-james", "user_role": "loan_officer"}

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.loan_officer_tools.check_completeness",
                new_callable=AsyncMock,
                return_value=mock_completeness,
            ),
            patch(
                "src.agents.loan_officer_tools.get_conditions",
                new_callable=AsyncMock,
                return_value=mock_conditions,
            ),
            patch(
                "src.agents.loan_officer_tools.get_rate_lock_status",
                new_callable=AsyncMock,
                return_value=mock_rate_lock,
            ),
            patch("src.agents.loan_officer_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_draft_communication.ainvoke(
                {
                    "application_id": 101,
                    "communication_type": "document_request",
                    "state": state,
                }
            )

        assert "客户信息：" in result
        assert "李晓雨" in result
        assert "贷款信息：" in result
        assert "住房公积金个人住房贷款" in result
        assert "¥425,000.00" in result
        assert "申请材料（已提供 2/4 项）：" in result
        assert "收入证明：已提供" in result
        assert "银行流水：缺失" in result
        assert "待处理审批条件（1 项）：" in result
        assert "审批前完成" in result
        assert "补充加盖单位公章的在职证明" in result
        assert "执行利率：" in result
        assert "3.100%" in result
        assert "优先处理" in result
        assert "敏感个人属性" in result

    @pytest.mark.asyncio
    async def test_invalid_communication_type(self):
        """Invalid type returns error without calling services."""
        state = {"user_id": "lo-james", "user_role": "loan_officer"}

        result = await lo_draft_communication.ainvoke(
            {
                "application_id": 101,
                "communication_type": "invalid_type",
                "state": state,
            }
        )

        assert "不支持的沟通类型" in result
        assert "invalid_type" in result

    @pytest.mark.asyncio
    async def test_app_not_found(self):
        """Out-of-scope app returns 'not found'."""
        state = {"user_id": "lo-james", "user_role": "loan_officer"}

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("src.agents.loan_officer_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_draft_communication.ainvoke(
                {
                    "application_id": 999,
                    "communication_type": "status_update",
                    "state": state,
                }
            )

        assert "未找到" in result


# ---------------------------------------------------------------------------
# lo_send_communication
# ---------------------------------------------------------------------------


class TestLoSendCommunication:
    """Audit-only communication send tool."""

    @pytest.mark.asyncio
    async def test_writes_audit_event(self):
        """Verifies write_audit_event called with correct event_type and data shape."""
        mock_app = MagicMock()

        state = {"user_id": "lo-james", "user_role": "loan_officer"}

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.loan_officer_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.loan_officer_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_send_communication.ainvoke(
                {
                    "application_id": 101,
                    "communication_type": "document_request",
                    "subject": "请补充申请材料",
                    "recipient_name": "李晓雨",
                    "state": state,
                }
            )

        assert "已记录" in result
        mock_audit.assert_awaited_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "communication_sent"
        event_data = audit_call.kwargs["event_data"]
        assert event_data["communication_type"] == "document_request"
        assert event_data["subject"] == "请补充申请材料"
        assert event_data["recipient_name"] == "李晓雨"
        assert event_data["delivery_method"] == "audit_only"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_app_not_found(self):
        """Out-of-scope app returns 'not found', no audit written."""
        state = {"user_id": "lo-james", "user_role": "loan_officer"}

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.agents.loan_officer_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.loan_officer_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await lo_send_communication.ainvoke(
                {
                    "application_id": 999,
                    "communication_type": "status_update",
                    "subject": "Test",
                    "recipient_name": "Nobody",
                    "state": state,
                }
            )

        assert "未找到" in result
        mock_audit.assert_not_awaited()
