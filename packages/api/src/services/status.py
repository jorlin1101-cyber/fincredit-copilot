# This project was developed with assistance from AI tools.
"""Application status aggregation service.

Combines stage info, document completeness, and open conditions into a
single status summary for the borrower or loan officer.
"""

import logging

from db import Application, Condition
from db.enums import ApplicationStage, ConditionStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import UserContext
from ..schemas.status import (
    ApplicationStatusResponse,
    PendingAction,
    StageInfo,
)
from ..services.application import get_application
from ..services.completeness import check_completeness

logger = logging.getLogger(__name__)

# 面向借款人的中文流程说明。
STAGE_INFO: dict[str, StageInfo] = {
    ApplicationStage.INQUIRY.value: StageInfo(
        label="咨询",
        description="您的住房贷款咨询已受理，客户经理将尽快联系您。",
        next_step="填写基本申请信息并提交贷款需求。",
        typical_timeline="预计1—2个工作日",
    ),
    ApplicationStage.PREQUALIFICATION.value: StageInfo(
        label="预审",
        description="正在依据您提供的收入、负债和首付款信息进行初步评估。",
        next_step="符合条件后将生成预审结果，供后续正式申请参考。",
        typical_timeline="预计1—3个工作日",
    ),
    ApplicationStage.APPLICATION.value: StageInfo(
        label="申请中",
        description="您的正式贷款申请正在办理，请按材料清单完成提交。",
        next_step="补齐申请材料后进入资料核验。",
        typical_timeline="视材料提交进度而定",
    ),
    ApplicationStage.PROCESSING.value: StageInfo(
        label="材料处理中",
        description="客户经理正在核验申请信息，并协调征信、评估等必要环节。",
        next_step="材料核验完成后提交授信审批。",
        typical_timeline="预计1—2周",
    ),
    ApplicationStage.UNDERWRITING.value: StageInfo(
        label="授信审批",
        description="审批人员正在依据授信政策评估还款能力、信用情况和房产信息。",
        next_step="审批过程中可能需要您补充材料或说明。",
        typical_timeline="预计1—2周",
    ),
    ApplicationStage.CONDITIONAL_APPROVAL.value: StageInfo(
        label="附条件审批通过",
        description="申请已附条件通过，仍需完成页面列出的待办事项。",
        next_step="按审批条件补充相应材料或信息。",
        typical_timeline="视条件复杂程度而定",
    ),
    ApplicationStage.CLEAR_TO_CLOSE.value: StageInfo(
        label="具备放款条件",
        description="主要审批条件已满足，申请已进入合同确认与放款准备阶段。",
        next_step="完成剩余条件，并核对、签署贷款合同及相关文件。",
        typical_timeline="预计3—5个工作日进入放款环节",
    ),
    ApplicationStage.CLOSED.value: StageInfo(
        label="已结案",
        description="贷款已完成放款并结案。",
        next_step="当前无需继续操作，请按合同约定还款。",
        typical_timeline="已完成",
    ),
    ApplicationStage.DENIED.value: StageInfo(
        label="未通过",
        description="本次贷款申请暂未通过审批。",
        next_step="请查看审批结果说明，或联系客户经理咨询。",
        typical_timeline="已完成",
    ),
    ApplicationStage.WITHDRAWN.value: StageInfo(
        label="已撤回",
        description="该笔申请已撤回。",
        next_step="当前无需操作，如有需要可重新发起申请。",
        typical_timeline="已完成",
    ),
}

_TERMINAL_STAGES = ApplicationStage.terminal_stages()

_RESOLVED_CONDITION_STATUSES = {
    ConditionStatus.CLEARED,
    ConditionStatus.WAIVED,
}


async def get_application_status(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    *,
    return_app: bool = False,
) -> ApplicationStatusResponse | None | tuple["ApplicationStatusResponse", "Application"]:
    """Build an aggregated status summary for an application.

    Returns None if the application is not found or not accessible.
    If return_app=True, returns (response, app) tuple to avoid redundant queries.
    """
    # Get document completeness (also validates app exists + scope)
    completeness = await check_completeness(session, user, application_id)
    if completeness is None:
        return None

    # check_completeness already validated access; load app for stage info
    app = await get_application(session, user, application_id)
    stage = app.stage.value if app.stage else ApplicationStage.INQUIRY.value

    stage_info = STAGE_INFO.get(
        stage,
        StageInfo(
            label="办理中",
            description="您的贷款申请正在办理。",
            next_step="如需了解详情，请联系客户经理。",
            typical_timeline="视实际办理情况而定",
        ),
    )

    # Count open conditions
    open_conditions_count = 0
    if stage not in _TERMINAL_STAGES:
        result = await session.execute(
            select(func.count())
            .select_from(Condition)
            .where(
                Condition.application_id == application_id,
                Condition.status.notin_([s for s in _RESOLVED_CONDITION_STATUSES]),
            )
        )
        open_conditions_count = result.scalar() or 0

    # Build pending actions
    pending_actions: list[PendingAction] = []
    if stage not in _TERMINAL_STAGES:
        # Missing documents
        missing_docs = [r for r in completeness.requirements if not r.is_provided]
        for req in missing_docs:
            pending_actions.append(
                PendingAction(
                    action_type="upload_document",
                    description=f"请上传{req.label}",
                )
            )

        # Quality issues on provided documents
        for req in completeness.requirements:
            if req.is_provided and req.quality_flags:
                flags = ", ".join(req.quality_flags)
                pending_actions.append(
                    PendingAction(
                        action_type="resubmit_document",
                        description=f"请重新提交{req.label}（{flags}）",
                    )
                )

        # Open conditions
        if open_conditions_count > 0:
            pending_actions.append(
                PendingAction(
                    action_type="clear_conditions",
                    description=f"有{open_conditions_count}项审批条件待处理",
                )
            )

    response = ApplicationStatusResponse(
        application_id=application_id,
        stage=stage,
        stage_info=stage_info,
        is_document_complete=completeness.is_complete,
        provided_doc_count=completeness.provided_count,
        required_doc_count=completeness.required_count,
        open_condition_count=open_conditions_count,
        pending_actions=pending_actions,
    )
    if return_app:
        return response, app
    return response
