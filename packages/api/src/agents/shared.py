# This project was developed with assistance from AI tools.
"""Shared utilities for agent tool modules.

Tools use ``SessionLocal()`` for DB access because LangGraph tool nodes run
outside a FastAPI request lifecycle -- there is no ``Request`` object and no
``Depends(get_db)`` injection available.  Route handlers, by contrast, receive
a session via ``Depends(get_db)``.  Both paths ultimately use the same engine
and connection pool; the difference is only how the session is obtained.
"""

from db.enums import UserRole

from ..core.auth import build_data_scope
from ..schemas.auth import UserContext


def user_context_from_state(state: dict, *, default_role: str) -> UserContext:
    """Build a UserContext from the agent's graph state.

    Args:
        state: The LangGraph graph state dict containing user_id, user_role, etc.
        default_role: Fallback role string if user_role is missing from state.

    Raises:
        ValueError: If user_id is missing from state.
    """
    user_id = state.get("user_id")
    if not user_id:
        raise ValueError("user_id is required in agent state")
    role_str = state.get("user_role", default_role)
    role = UserRole(role_str)
    return UserContext(
        user_id=user_id,
        role=role,
        email=state.get("user_email") or f"{user_id}@example.com",
        name=state.get("user_name") or user_id,
        data_scope=build_data_scope(role, user_id),
    )


_ENUM_LABELS = {
    # Application lifecycle
    "inquiry": "咨询",
    "prequalification": "预审",
    "application": "申请中",
    "processing": "材料处理中",
    "underwriting": "授信审批",
    "conditional_approval": "附条件通过",
    "clear_to_close": "具备签约条件",
    "closed": "已结案",
    "denied": "未通过",
    "withdrawn": "已撤回",
    # Document and condition states
    "uploaded": "已上传",
    "processing_complete": "识别完成",
    "processing_failed": "识别失败",
    "pending_review": "待复核",
    "accepted": "已通过",
    "flagged_for_resubmission": "需重新提交",
    "rejected": "未通过",
    "open": "待处理",
    "responded": "已响应",
    "under_review": "复核中",
    "cleared": "已完成",
    "waived": "已豁免",
    "escalated": "已升级",
    # Condition timing
    "prior_to_approval": "审批前完成",
    "prior_to_docs": "合同文件生成前完成",
    "prior_to_closing": "签约前完成",
    "prior_to_funding": "放款前完成",
    # Employment and decisions
    "w2_employee": "工薪就业",
    "self_employed": "自主经营",
    "retired": "退休",
    "unemployed": "待业",
    "other": "其他",
    "approved": "通过",
    "suspended": "暂缓",
    # Common document types retained for legacy records
    "id_card": "身份证",
    "income_certificate": "收入证明",
    "w2": "收入证明（兼容类型）",
    "pay_stub": "工资单",
    "tax_return": "纳税证明",
    "bank_statement": "银行流水",
    "drivers_license": "驾驶证（兼容类型）",
    "passport": "护照",
    "property_appraisal": "房产评估报告",
    "homeowners_insurance": "房屋保险凭证",
    "title_insurance": "产权相关材料（兼容类型）",
    "flood_insurance": "专项保险材料（兼容类型）",
    "purchase_agreement": "购房合同",
    "gift_letter": "赠与说明",
}


def format_enum_label(value: str) -> str:
    """Return a user-facing Chinese label for a persisted enum value.

    Unknown values are normalized without Title Case so internal identifiers do
    not unexpectedly turn into English product copy.
    """
    normalized = str(value or "").strip().lower()
    return _ENUM_LABELS.get(normalized, normalized.replace("_", " "))
