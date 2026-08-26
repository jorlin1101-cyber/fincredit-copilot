# This project was developed with assistance from AI tools.
"""Disclosure acknowledgment service.

Tracks borrower acknowledgment of required lending disclosures
(Loan Estimate, privacy notice, HMDA notice, equal opportunity notice)
via the append-only audit trail.  Each acknowledgment is a separate
audit event with event_type='disclosure_acknowledged'.
"""

from db import AuditEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings

# 借款人工作台使用的演示告知文件。保留既有 ID 以兼容审计记录，
# 但展示内容采用中国个人住房贷款场景，不代表真实银行合同或法律意见。
REQUIRED_DISCLOSURES: list[dict[str, str]] = [
    {
        "id": "loan_estimate",
        "label": "个人住房贷款要素确认书",
        "summary": ("汇总贷款金额、期限、利率方式、还款安排及相关费用，供申请人核对。"),
        "content": (
            "个人住房贷款要素确认书\n\n"
            "【演示说明】本文件仅用于虚构金融科技项目演示，不构成授信承诺、"
            "贷款合同或法律意见。\n\n"
            "一、核对范围\n"
            "请重点核对借款人信息、贷款用途、贷款金额、贷款期限、执行利率及"
            "调整方式、还款方式、放款条件、提前还款安排和逾期责任。\n\n"
            "二、还款提示\n"
            "页面展示的月供和总利息均为测算结果。实际还款计划以正式贷款合同、"
            "放款金额、执行利率和实际放款日生成的还款计划表为准。\n\n"
            "三、费用提示\n"
            "请确认评估、抵押登记、保险等可能发生的费用及承担主体。任何费用均应"
            "以合法有效的合同、收费公示或第三方正式凭证为依据。\n\n"
            "四、风险提示\n"
            "利率调整、收入变化或其他负债增加均可能影响还款能力。请结合家庭现金流"
            "审慎确定贷款金额和期限。"
        ),
    },
    {
        "id": "privacy_notice",
        "label": "个人金融信息保护告知书",
        "summary": (f"说明{settings.COMPANY_NAME}在演示流程中处理个人信息的目的、范围与保护措施。"),
        "content": (
            "个人金融信息保护告知书\n\n"
            "【演示说明】本项目为虚构演示系统，不接收真实身份证号、银行卡号、征信报告"
            "或其他敏感个人信息。\n\n"
            "一、处理目的\n"
            "用于演示住房贷款申请、材料校验、风险评估、进度查询和智能问答。\n\n"
            "二、信息范围\n"
            "演示数据可能包括身份信息、联系方式、收入与负债、住房交易信息及上传材料。"
            "请勿上传任何真实个人敏感信息。\n\n"
            "三、处理原则\n"
            "遵循合法、正当、必要和诚信原则，仅在实现演示功能所需范围内处理数据，并通过"
            "访问控制、传输加密和操作审计等措施降低数据风险。\n\n"
            "四、您的权利\n"
            "在适用情形下，个人可依法申请查阅、复制、更正、补充或删除其个人信息。\n\n"
            "参考依据：《中华人民共和国个人信息保护法》《中华人民共和国数据安全法》及"
            "中国人民银行金融消费者权益保护相关规定。"
        ),
    },
    {
        "id": "hmda_notice",
        "label": "个人征信查询与报送授权书",
        "summary": ("说明征信查询、使用及信贷信息报送的目的和授权边界。"),
        "content": (
            "个人征信查询与报送授权书\n\n"
            "【演示说明】本授权书为项目演示文本，系统不会连接真实征信机构。\n\n"
            "一、授权事项\n"
            "在正式业务中，金融机构应在取得有效授权并符合法律规定的前提下，为贷款审查、"
            "贷后管理等约定用途查询和使用个人信用信息，并按规定报送信贷业务信息。\n\n"
            "二、使用限制\n"
            "征信信息不得超出授权目的使用，不得以未经授权的方式向无关第三方提供。\n\n"
            "三、异议权利\n"
            "如认为信用报告中的信息存在错误、遗漏，信息主体可依法向征信机构或信息提供者"
            "提出异议。\n\n"
            "参考依据：《征信业管理条例》及中国人民银行征信业务管理相关规定。"
        ),
    },
    {
        "id": "equal_opportunity_notice",
        "label": "金融消费者权益告知书",
        "summary": ("说明知情权、自主选择权、公平交易权、信息安全权及投诉渠道等基本权益。"),
        "content": (
            "金融消费者权益告知书\n\n"
            "【演示说明】本文件用于展示金融消费者权益保护环节，不替代金融机构正式告知。\n\n"
            "一、知情权\n"
            "有权了解贷款产品的利率、期限、费用、还款方式、违约责任和主要风险。\n\n"
            "二、自主选择与公平交易\n"
            "有权根据自身需求选择适当产品，不应被强制搭售或承担未明确告知的费用。授信评估"
            "应基于与还款能力和信用风险相关的合法、必要信息。\n\n"
            "三、信息安全\n"
            "个人金融信息应依法受到保护。请通过官方渠道提交材料，谨防以贷款名义索要密码、"
            "短信验证码或要求向个人账户转账。\n\n"
            "四、投诉与争议解决\n"
            "如对产品、服务或处理结果存在异议，可先通过金融机构公布的客服和投诉渠道反映；"
            "也可依法通过调解、仲裁或诉讼等方式解决。\n\n"
            "参考依据：中国人民银行金融消费者权益保护相关规定及现行消费者权益保护法律法规。"
        ),
    },
]

_DISCLOSURE_IDS = {d["id"] for d in REQUIRED_DISCLOSURES}
DISCLOSURE_BY_ID = {d["id"]: d for d in REQUIRED_DISCLOSURES}


async def get_disclosure_status(
    session: AsyncSession,
    application_id: int,
) -> dict:
    """Return disclosure acknowledgment status for an application.

    Queries audit_events for event_type='disclosure_acknowledged' rows
    linked to the given application_id.

    Returns:
        {
            "application_id": int,
            "all_acknowledged": bool,
            "acknowledged": ["loan_estimate", ...],
            "pending": ["privacy_notice", ...],
        }
    """
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.event_type == "disclosure_acknowledged",
            AuditEvent.application_id == application_id,
        )
        .order_by(AuditEvent.timestamp.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    acknowledged_ids: set[str] = set()
    for event in events:
        if event.event_data and isinstance(event.event_data, dict):
            disc_id = event.event_data.get("disclosure_id")
            if disc_id in _DISCLOSURE_IDS:
                acknowledged_ids.add(disc_id)

    pending = [d_id for d_id in _DISCLOSURE_IDS if d_id not in acknowledged_ids]

    return {
        "application_id": application_id,
        "all_acknowledged": len(pending) == 0,
        "acknowledged": sorted(acknowledged_ids),
        "pending": sorted(pending),
    }
