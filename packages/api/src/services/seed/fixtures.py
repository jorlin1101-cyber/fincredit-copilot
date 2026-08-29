# This project was developed with assistance from AI tools.
"""
Demo fixture data for multi-agent loan origination.

All fixture data is defined as Python dicts so enums can be referenced directly
and type-checked. Keycloak user IDs are deterministic UUIDs that match the
"id" fields in config/keycloak/mortgage-ai-realm.json.

Simulated for demonstration purposes -- not real financial data.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from db.enums import (
    ApplicationStage,
    ConditionSeverity,
    ConditionStatus,
    DecisionType,
    DocumentStatus,
    DocumentType,
    LoanType,
)

# ---------------------------------------------------------------------------
# Keycloak user references (deterministic UUIDs)
# ---------------------------------------------------------------------------
# These UUIDs match the "id" fields in config/keycloak/mortgage-ai-realm.json.
# Keycloak's JWT "sub" claim returns the user ID, and the application service
# filters by borrower.keycloak_user_id == sub. Using fixed IDs ensures the
# seeded data links correctly to authenticated users.

SARAH_MITCHELL_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567801"
JAMES_TORRES_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567802"
MARIA_CHEN_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567803"
DAVID_PARK_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567804"
ADMIN_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567805"

# 共同借款人（李晓雨的配偶）
JENNIFER_MITCHELL_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567806"

# Additional loan officers
SARAH_PATEL_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567807"
MARCUS_WILLIAMS_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567808"

# Fictional borrowers (not in Keycloak -- only used for historical loan data)
MICHAEL_JOHNSON_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567811"
EMILY_RODRIGUEZ_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567812"
ROBERT_KIM_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567813"
LISA_WASHINGTON_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567814"
THOMAS_NGUYEN_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567815"
AMANDA_FOSTER_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567816"
DANIEL_RAMIREZ_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567817"
PATRICIA_CHANG_ID = "d1a2b3c4-e5f6-7890-abcd-ef1234567818"


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def _days_ago(n: int) -> datetime:
    return _NOW - timedelta(days=n)


def _days_from_now(n: int) -> datetime:
    return _NOW + timedelta(days=n)


# ---------------------------------------------------------------------------
# Extraction templates per document type
# ---------------------------------------------------------------------------


def _w2_extractions(
    employer: str,
    annual_income: str,
    tax_year: str = "2025",
    ein: str = "84-1234567",
) -> list[dict]:
    return [
        {
            "field_name": "employer_name",
            "field_value": employer,
            "confidence": 0.97,
            "source_page": 1,
        },
        {
            "field_name": "annual_income",
            "field_value": annual_income,
            "confidence": 0.95,
            "source_page": 1,
        },
        {"field_name": "tax_year", "field_value": tax_year, "confidence": 0.99, "source_page": 1},
        {"field_name": "ein", "field_value": ein, "confidence": 0.93, "source_page": 1},
    ]


def _pay_stub_extractions(
    employer: str,
    gross_pay: str,
    pay_period: str = "每月",
    ytd: str | None = None,
) -> list[dict]:
    fields = [
        {
            "field_name": "employer_name",
            "field_value": employer,
            "confidence": 0.96,
            "source_page": 1,
        },
        {"field_name": "gross_pay", "field_value": gross_pay, "confidence": 0.94, "source_page": 1},
        {
            "field_name": "pay_period",
            "field_value": pay_period,
            "confidence": 0.98,
            "source_page": 1,
        },
    ]
    if ytd:
        fields.append(
            {
                "field_name": "ytd_earnings",
                "field_value": ytd,
                "confidence": 0.92,
                "source_page": 1,
            },
        )
    return fields


def _bank_statement_extractions(
    institution: str,
    balance: str,
    period: str = "2026年1月",
    account_type: str = "个人结算账户",
) -> list[dict]:
    return [
        {
            "field_name": "institution",
            "field_value": institution,
            "confidence": 0.98,
            "source_page": 1,
        },
        {
            "field_name": "account_type",
            "field_value": account_type,
            "confidence": 0.97,
            "source_page": 1,
        },
        {
            "field_name": "ending_balance",
            "field_value": balance,
            "confidence": 0.91,
            "source_page": 2,
        },
        {
            "field_name": "statement_period",
            "field_value": period,
            "confidence": 0.99,
            "source_page": 1,
        },
    ]


def _id_extractions(
    full_name: str,
    state: str = "四川省",
    expiration: str = "2028年9月15日",
) -> list[dict]:
    return [
        {"field_name": "full_name", "field_value": full_name, "confidence": 0.96, "source_page": 1},
        {"field_name": "issuing_state", "field_value": state, "confidence": 0.99, "source_page": 1},
        {
            "field_name": "expiration_date",
            "field_value": expiration,
            "confidence": 0.88,
            "source_page": 1,
        },
    ]


def _tax_return_extractions(
    filer_name: str,
    agi: str,
    tax_year: str = "2025",
) -> list[dict]:
    return [
        {
            "field_name": "filer_name",
            "field_value": filer_name,
            "confidence": 0.95,
            "source_page": 1,
        },
        {
            "field_name": "adjusted_gross_income",
            "field_value": agi,
            "confidence": 0.87,
            "source_page": 2,
        },
        {"field_name": "tax_year", "field_value": tax_year, "confidence": 0.99, "source_page": 1},
        {
            "field_name": "filing_status",
            "field_value": "居民个人申报",
            "confidence": 0.93,
            "source_page": 1,
        },
    ]


# ---------------------------------------------------------------------------
# Borrower profiles
# ---------------------------------------------------------------------------

BORROWERS: list[dict] = [
    {
        "keycloak_user_id": SARAH_MITCHELL_ID,
        "first_name": "晓雨",
        "last_name": "李",
        "email": "li.xiaoyu@example.com",
        "ssn": "ENC:DEMO-ID-001",
        "dob": datetime(1988, 6, 15, tzinfo=UTC),
    },
    {
        "keycloak_user_id": JENNIFER_MITCHELL_ID,
        "first_name": "晓雯",
        "last_name": "李",
        "email": "li.xiaowen@example.com",
        "ssn": "ENC:DEMO-ID-002",
        "dob": datetime(1990, 2, 8, tzinfo=UTC),
    },
    {
        "keycloak_user_id": "d1a2b3c4-e5f6-7890-abcd-ef1234567811",
        "first_name": "志远",
        "last_name": "王",
        "email": "wang.zhiyuan@example.com",
        "ssn": "ENC:DEMO-ID-003",
        "dob": datetime(1975, 11, 3, tzinfo=UTC),
    },
    {
        "keycloak_user_id": "d1a2b3c4-e5f6-7890-abcd-ef1234567812",
        "first_name": "静怡",
        "last_name": "陈",
        "email": "chen.jingyi@example.com",
        "ssn": "ENC:DEMO-ID-004",
        "dob": datetime(1992, 3, 22, tzinfo=UTC),
    },
    {
        "keycloak_user_id": "d1a2b3c4-e5f6-7890-abcd-ef1234567813",
        "first_name": "浩然",
        "last_name": "刘",
        "email": "liu.haoran@example.com",
        "ssn": "ENC:DEMO-ID-005",
        "dob": datetime(1983, 9, 8, tzinfo=UTC),
    },
    {
        "keycloak_user_id": "d1a2b3c4-e5f6-7890-abcd-ef1234567814",
        "first_name": "欣怡",
        "last_name": "赵",
        "email": "zhao.xinyi@example.com",
        "ssn": "ENC:DEMO-ID-006",
        "dob": datetime(1990, 1, 27, tzinfo=UTC),
    },
    {
        "keycloak_user_id": "d1a2b3c4-e5f6-7890-abcd-ef1234567815",
        "first_name": "宇航",
        "last_name": "周",
        "email": "zhou.yuhang@example.com",
        "ssn": "ENC:DEMO-ID-007",
        "dob": datetime(1979, 7, 14, tzinfo=UTC),
    },
    {
        "keycloak_user_id": AMANDA_FOSTER_ID,
        "first_name": "雨桐",
        "last_name": "孙",
        "email": "sun.yutong@example.com",
        "ssn": "ENC:DEMO-ID-008",
        "dob": datetime(1985, 4, 19, tzinfo=UTC),
    },
    {
        "keycloak_user_id": DANIEL_RAMIREZ_ID,
        "first_name": "子轩",
        "last_name": "吴",
        "email": "wu.zixuan@example.com",
        "ssn": "ENC:DEMO-ID-009",
        "dob": datetime(1991, 8, 2, tzinfo=UTC),
    },
    {
        "keycloak_user_id": PATRICIA_CHANG_ID,
        "first_name": "思琪",
        "last_name": "郑",
        "email": "zheng.siqi@example.com",
        "ssn": "ENC:DEMO-ID-010",
        "dob": datetime(1987, 12, 11, tzinfo=UTC),
    },
]

# ---------------------------------------------------------------------------
# Active applications (10) -- distributed across 3 loan officers
# ---------------------------------------------------------------------------

# borrower_ref is the keycloak_user_id of the borrower; the seeder resolves
# it to the borrower.id FK at insert time.

ACTIVE_APPLICATIONS: list[dict] = [
    # --- 4 in APPLICATION stage ---
    {
        "borrower_ref": SARAH_MITCHELL_ID,
        "co_borrower_refs": [JENNIFER_MITCHELL_ID],
        "stage": ApplicationStage.APPLICATION,
        "loan_type": LoanType.CONVENTIONAL_30,
        "property_address": "成都市高新区天府三街演示家园5栋2单元（虚构地址）",
        "loan_amount": Decimal("1800000.00"),
        "property_value": Decimal("2600000.00"),
        "assigned_to": JAMES_TORRES_ID,
        "created_at": _days_ago(14),
        "updated_at": _days_ago(0),
        "financials": {
            "gross_monthly_income": Decimal("28000.00"),
            "monthly_debts": Decimal("4800.00"),
            "total_assets": Decimal("1250000.00"),
            "credit_score": 742,
            "dti_ratio": 0.282,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions("成都远景科技有限公司", "¥336,000"),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都远景科技有限公司", "¥28,000", ytd="¥168,000"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                "quality_flags": json.dumps(["outdated_statement"]),
                "extractions": [
                    {
                        "field_name": "institution",
                        "field_value": "中国建设银行成都分行（演示）",
                        "confidence": 0.98,
                        "source_page": 1,
                    },
                    {
                        "field_name": "account_type",
                        "field_value": "个人结算账户",
                        "confidence": 0.97,
                        "source_page": 1,
                    },
                    {
                        "field_name": "ending_balance",
                        "field_value": "¥472,500.00",
                        "confidence": 0.93,
                        "source_page": 2,
                    },
                    {
                        "field_name": "statement_period",
                        "field_value": "2026年7月",
                        "confidence": 0.99,
                        "source_page": 1,
                    },
                ],
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("李晓雨", expiration="2029-07-14", state="四川"),
            },
        ],
    },
    {
        "borrower_ref": EMILY_RODRIGUEZ_ID,
        "stage": ApplicationStage.APPLICATION,
        "loan_type": LoanType.FHA,
        "property_address": "成都市锦江区东大街演示公馆2栋1单元（虚构地址）",
        "loan_amount": Decimal("2450000.00"),
        "property_value": Decimal("3100000.00"),
        "assigned_to": SARAH_PATEL_ID,
        "created_at": _days_ago(10),
        "updated_at": _days_ago(5),
        "financials": {
            "gross_monthly_income": Decimal("6200.00"),
            "monthly_debts": Decimal("1800.00"),
            "total_assets": Decimal("42000.00"),
            "credit_score": 688,
            "dti_ratio": 0.290,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.UPLOADED,
                "extractions": _w2_extractions("成都安康医疗服务有限公司（演示）", "¥168,000"),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                "quality_flags": json.dumps(["wrong_account_period", "missing_pages"]),
                "extractions": [
                    {
                        "field_name": "institution",
                        "field_value": "中国工商银行成都分行（演示）",
                        "confidence": 0.95,
                        "source_page": 1,
                    },
                    {
                        "field_name": "account_type",
                        "field_value": "个人结算账户",
                        "confidence": 0.92,
                        "source_page": 1,
                    },
                    {
                        "field_name": "ending_balance",
                        "field_value": "¥123,400.00",
                        "confidence": 0.68,
                        "source_page": 1,
                    },
                    {
                        "field_name": "statement_period",
                        "field_value": "2026年6月",
                        "confidence": 0.44,
                        "source_page": 1,
                    },
                ],
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("陈静怡", state="四川"),
            },
        ],
    },
    {
        "borrower_ref": SARAH_MITCHELL_ID,
        "stage": ApplicationStage.APPLICATION,
        "loan_type": LoanType.CONVENTIONAL_15,
        "property_address": "成都市武侯区人民南路演示花园3栋2单元（虚构地址）",
        "loan_amount": Decimal("2000000.00"),
        "property_value": Decimal("2850000.00"),
        "assigned_to": SARAH_PATEL_ID,
        "created_at": _days_ago(7),
        "updated_at": _days_ago(3),
        "financials": {
            "gross_monthly_income": Decimal("8500.00"),
            "monthly_debts": Decimal("2400.00"),
            "total_assets": Decimal("95000.00"),
            "credit_score": 742,
            "dti_ratio": 0.282,
        },
        "documents": [
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                "quality_flags": json.dumps(["partially_illegible"]),
                "extractions": [
                    {
                        "field_name": "employer_name",
                        "field_value": "成都智创科技有限公司（演示）",
                        "confidence": 0.72,
                        "source_page": 1,
                    },
                    {
                        "field_name": "gross_pay",
                        "field_value": None,
                        "confidence": 0.31,
                        "source_page": 1,
                    },
                    {
                        "field_name": "pay_period",
                        "field_value": "月度",
                        "confidence": 0.85,
                        "source_page": 1,
                    },
                ],
            },
        ],
    },
    {
        "borrower_ref": AMANDA_FOSTER_ID,
        "stage": ApplicationStage.APPLICATION,
        "loan_type": LoanType.ARM,
        "property_address": "成都市青羊区光华大道演示新城6栋1单元（虚构地址）",
        "loan_amount": Decimal("3600000.00"),
        "property_value": Decimal("4500000.00"),
        "assigned_to": MARCUS_WILLIAMS_ID,
        "created_at": _days_ago(5),
        "updated_at": _days_ago(2),
        "financials": {
            "gross_monthly_income": Decimal("9200.00"),
            "monthly_debts": Decimal("2100.00"),
            "total_assets": Decimal("78000.00"),
            "credit_score": 735,
            "dti_ratio": 0.228,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.UPLOADED,
                "extractions": _w2_extractions(
                    "成都雨桐设计有限公司（演示）", "¥240,000", ein="演示编号"
                ),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.UPLOADED,
                "extractions": _pay_stub_extractions(
                    "成都雨桐设计有限公司（演示）", "¥20,000", ytd="¥160,000"
                ),
            },
            {
                "doc_type": DocumentType.TAX_RETURN,
                "status": DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                "quality_flags": json.dumps(["unsigned_document"]),
                "extractions": [
                    {
                        "field_name": "filer_name",
                        "field_value": "孙雨桐",
                        "confidence": 0.94,
                        "source_page": 1,
                    },
                    {
                        "field_name": "adjusted_gross_income",
                        "field_value": "¥238,000",
                        "confidence": 0.89,
                        "source_page": 2,
                    },
                    {
                        "field_name": "tax_year",
                        "field_value": "2025",
                        "confidence": 0.99,
                        "source_page": 1,
                    },
                    {
                        "field_name": "filing_status",
                        "field_value": "居民个人申报",
                        "confidence": 0.91,
                        "source_page": 1,
                    },
                    {
                        "field_name": "signature_present",
                        "field_value": "否",
                        "confidence": 0.97,
                        "source_page": 4,
                    },
                ],
            },
        ],
    },
    # --- 3 in UNDERWRITING stage ---
    {
        "borrower_ref": ROBERT_KIM_ID,
        "stage": ApplicationStage.UNDERWRITING,
        "loan_type": LoanType.CONVENTIONAL_30,
        "property_address": "成都市成华区建设路演示家园9栋2单元（虚构地址）",
        "loan_amount": Decimal("4750000.00"),
        "property_value": Decimal("5800000.00"),
        "assigned_to": MARCUS_WILLIAMS_ID,
        "created_at": _days_ago(28),
        "updated_at": _days_ago(6),
        "financials": {
            "gross_monthly_income": Decimal("5200.00"),
            "monthly_debts": Decimal("3200.00"),
            "total_assets": Decimal("18000.00"),
            "credit_score": 520,
            "dti_ratio": 0.615,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions("成都华景工程技术有限公司（演示）", "¥62,400"),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都华景工程技术有限公司（演示）", "¥5,200.00", ytd="¥31,200.00"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _bank_statement_extractions(
                    "成都银行建设路支行（演示）", "¥92,400.00", account_type="个人储蓄账户"
                ),
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("刘浩然", expiration="2029年3月20日"),
            },
        ],
        "conditions": [
            {
                "description": "核验借款人当前工作及收入情况",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(5),
            },
            {
                "description": "补充最近两个月的银行流水",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.RESPONDED,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(3),
            },
        ],
    },
    {
        "borrower_ref": LISA_WASHINGTON_ID,
        "stage": ApplicationStage.UNDERWRITING,
        "loan_type": LoanType.VA,
        "property_address": "成都市金牛区一品天下大街演示名苑4栋1单元（虚构地址）",
        "loan_amount": Decimal("3800000.00"),
        "property_value": Decimal("4600000.00"),
        "assigned_to": JAMES_TORRES_ID,
        "created_at": _days_ago(21),
        "updated_at": _days_ago(4),
        "financials": {
            "gross_monthly_income": Decimal("9800.00"),
            "monthly_debts": Decimal("2900.00"),
            "total_assets": Decimal("120000.00"),
            "credit_score": 710,
            "dti_ratio": 0.296,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.PENDING_REVIEW,
                "quality_flags": json.dumps(["low_resolution"]),
                "extractions": [
                    {
                        "field_name": "employer_name",
                        "field_value": "成都优抚服务中心（演示）",
                        "confidence": 0.73,
                        "source_page": 1,
                    },
                    {
                        "field_name": "annual_income",
                        "field_value": "¥117,600",
                        "confidence": 0.88,
                        "source_page": 1,
                    },
                    {
                        "field_name": "tax_year",
                        "field_value": "2025",
                        "confidence": 0.99,
                        "source_page": 1,
                    },
                    {
                        "field_name": "ein",
                        "field_value": None,
                        "confidence": 0.35,
                        "source_page": 1,
                    },
                ],
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都优抚服务中心（演示）", "¥9,800.00", ytd="¥58,800.00"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": [
                    {
                        "field_name": "institution",
                        "field_value": "中国邮政储蓄银行成都分行（演示）",
                        "confidence": 0.97,
                        "source_page": 1,
                    },
                    {
                        "field_name": "account_type",
                        "field_value": "个人结算账户",
                        "confidence": 0.96,
                        "source_page": 1,
                    },
                    {
                        "field_name": "ending_balance",
                        "field_value": "¥58,100.00",
                        "confidence": 0.67,
                        "source_page": 3,
                    },
                    {
                        "field_name": "statement_period",
                        "field_value": "2026年1月",
                        "confidence": 0.98,
                        "source_page": 1,
                    },
                ],
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("赵欣怡", expiration="2027年11月30日"),
            },
        ],
        "conditions": [
            {
                "description": "补充优待客群资格证明材料",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(7),
            },
            {
                "description": "房产评估结果须符合贷款方案要求",
                "severity": ConditionSeverity.PRIOR_TO_DOCS,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(10),
            },
            {
                "description": "核验借款人其他负债及对外担保情况",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": MARIA_CHEN_ID,
            },
        ],
    },
    {
        "borrower_ref": DANIEL_RAMIREZ_ID,
        "stage": ApplicationStage.UNDERWRITING,
        "loan_type": LoanType.USDA,
        "property_address": "成都市双流区东升街道演示华庭7栋2单元（虚构地址）",
        "loan_amount": Decimal("2650000.00"),
        "property_value": Decimal("3200000.00"),
        "assigned_to": SARAH_PATEL_ID,
        "created_at": _days_ago(18),
        "updated_at": _days_ago(3),
        "financials": {
            "gross_monthly_income": Decimal("7100.00"),
            "monthly_debts": Decimal("1950.00"),
            "total_assets": Decimal("35000.00"),
            "credit_score": 695,
            "dti_ratio": 0.275,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions(
                    "成都新禾供应链有限公司（演示）", "¥85,200", ein="91510100DEMO123456"
                ),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都新禾供应链有限公司（演示）", "¥7,100.00", ytd="¥42,600.00"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _bank_statement_extractions(
                    "中国农业银行成都分行（演示）", "¥35,000.00"
                ),
            },
            {
                "doc_type": DocumentType.TAX_RETURN,
                "status": DocumentStatus.PENDING_REVIEW,
                "quality_flags": json.dumps(["blurry_scan"]),
                "extractions": [
                    {
                        "field_name": "filer_name",
                        "field_value": "吴子轩",
                        "confidence": 0.82,
                        "source_page": 1,
                    },
                    {
                        "field_name": "adjusted_gross_income",
                        "field_value": "¥82,100",
                        "confidence": 0.61,
                        "source_page": 2,
                    },
                    {
                        "field_name": "tax_year",
                        "field_value": "2025",
                        "confidence": 0.95,
                        "source_page": 1,
                    },
                    {
                        "field_name": "filing_status",
                        "field_value": None,
                        "confidence": 0.28,
                        "source_page": 1,
                    },
                ],
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("吴子轩", expiration="2028年6月10日"),
            },
        ],
        "conditions": [
            {
                "description": "核验县域住房贷款房产资格",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(4),
            },
            {
                "description": "核验家庭收入与贷款方案准入要求",
                "severity": ConditionSeverity.PRIOR_TO_APPROVAL,
                "status": ConditionStatus.RESPONDED,
                "issued_by": MARIA_CHEN_ID,
            },
        ],
    },
    # --- 2 in CONDITIONAL_APPROVAL stage ---
    {
        "borrower_ref": MICHAEL_JOHNSON_ID,
        "co_borrower_refs": [EMILY_RODRIGUEZ_ID],
        "stage": ApplicationStage.CONDITIONAL_APPROVAL,
        "loan_type": LoanType.JUMBO,
        "property_address": "成都市温江区光华大道演示雅居5栋1单元（虚构地址）",
        "loan_amount": Decimal("6500000.00"),
        "property_value": Decimal("8200000.00"),
        "assigned_to": SARAH_PATEL_ID,
        "created_at": _days_ago(42),
        "updated_at": _days_ago(7),
        "financials": {
            "gross_monthly_income": Decimal("18000.00"),
            "monthly_debts": Decimal("5400.00"),
            "total_assets": Decimal("450000.00"),
            "credit_score": 780,
            "dti_ratio": 0.300,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions(
                    "成都志远企业管理咨询有限公司（演示）", "¥216,000", ein="91510100DEMO778899"
                ),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都志远企业管理咨询有限公司（演示）", "¥18,000.00", ytd="¥108,000.00"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _bank_statement_extractions(
                    "招商银行成都分行（演示）", "¥450,000.00", account_type="个人理财账户"
                ),
            },
            {
                "doc_type": DocumentType.TAX_RETURN,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _tax_return_extractions("王志远", "¥210,500"),
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("王志远", expiration="2029年1月15日"),
            },
        ],
        "conditions": [
            {
                "description": "补充最终不动产权属核验材料",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(12),
            },
            {
                "description": "补充含抵押权人信息的房屋保险凭证",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": MARIA_CHEN_ID,
            },
        ],
        "decisions": [
            {
                "decision_type": DecisionType.CONDITIONAL_APPROVAL,
                "rationale": "申请人的还款能力与征信情况符合演示规则；签约前仍需完成房屋权属及保险材料核验。",
                "decided_by": MARIA_CHEN_ID,
            },
        ],
        "rate_lock": {
            "locked_rate": 6.875,
            "lock_date": _days_ago(10),
            "expiration_date": _days_from_now(35),
            "is_active": True,
        },
    },
    {
        "borrower_ref": THOMAS_NGUYEN_ID,
        "stage": ApplicationStage.CONDITIONAL_APPROVAL,
        "loan_type": LoanType.CONVENTIONAL_30,
        "property_address": "成都市龙泉驿区驿都大道演示新居8栋2单元（虚构地址）",
        "loan_amount": Decimal("3500000.00"),
        "property_value": Decimal("4250000.00"),
        "assigned_to": MARCUS_WILLIAMS_ID,
        "created_at": _days_ago(35),
        "updated_at": _days_ago(5),
        "financials": {
            "gross_monthly_income": Decimal("10500.00"),
            "monthly_debts": Decimal("3150.00"),
            "total_assets": Decimal("160000.00"),
            "credit_score": 725,
            "dti_ratio": 0.300,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions("成都百城软件科技有限公司（演示）", "¥126,000"),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都百城软件科技有限公司（演示）", "¥10,500.00", ytd="¥63,000.00"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _bank_statement_extractions(
                    "成都银行龙泉驿支行（演示）", "¥160,000.00"
                ),
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("周宇航", expiration="2028年4月22日"),
            },
        ],
        "conditions": [
            {
                "description": "补充签约前30日内的最新收入证明",
                "severity": ConditionSeverity.PRIOR_TO_DOCS,
                "status": ConditionStatus.RESPONDED,
                "issued_by": MARIA_CHEN_ID,
                "due_date": _days_from_now(8),
            },
            {
                "description": "补充房屋相关风险区域核验材料",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": JAMES_TORRES_ID,
            },
        ],
        "decisions": [
            {
                "decision_type": DecisionType.CONDITIONAL_APPROVAL,
                "rationale": "风险状况符合演示准入规则，仍需完成页面所列常规审批条件。",
                "decided_by": MARIA_CHEN_ID,
            },
        ],
        "rate_lock": {
            "locked_rate": 7.125,
            "lock_date": _days_ago(5),
            "expiration_date": _days_from_now(40),
            "is_active": True,
        },
    },
    # --- 1 in CLEAR_TO_CLOSE stage ---
    {
        "borrower_ref": SARAH_MITCHELL_ID,
        "stage": ApplicationStage.CLEAR_TO_CLOSE,
        "loan_type": LoanType.CONVENTIONAL_30,
        "property_address": "成都市高新区天府三街演示家园8栋1单元1204号（虚构地址）",
        "loan_amount": Decimal("2450000.00"),
        "property_value": Decimal("3500000.00"),
        "assigned_to": JAMES_TORRES_ID,
        "created_at": _days_ago(60),
        "updated_at": _days_ago(2),
        "financials": {
            "gross_monthly_income": Decimal("28000.00"),
            "monthly_debts": Decimal("4800.00"),
            "total_assets": Decimal("1250000.00"),
            "credit_score": 742,
            "dti_ratio": 0.282,
        },
        "documents": [
            {
                "doc_type": DocumentType.INCOME_CERTIFICATE,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _w2_extractions("成都远景科技有限公司", "¥336,000"),
            },
            {
                "doc_type": DocumentType.PAY_STUB,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _pay_stub_extractions(
                    "成都远景科技有限公司", "¥28,000", ytd="¥280,000"
                ),
            },
            {
                "doc_type": DocumentType.BANK_STATEMENT,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _bank_statement_extractions("演示商业银行成都分行", "¥1,250,000"),
            },
            {
                "doc_type": DocumentType.TAX_RETURN,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _tax_return_extractions("李晓雨", "¥336,000"),
            },
            {
                "doc_type": DocumentType.ID_CARD,
                "status": DocumentStatus.ACCEPTED,
                "extractions": _id_extractions("李晓雨", expiration="2030-02-28", state="四川"),
            },
            {
                "doc_type": DocumentType.PROPERTY_APPRAISAL,
                "status": DocumentStatus.ACCEPTED,
                "extractions": [
                    {
                        "field_name": "appraised_value",
                        "field_value": "¥3,500,000",
                        "confidence": 0.96,
                        "source_page": 3,
                    },
                    {
                        "field_name": "property_type",
                        "field_value": "成套住宅",
                        "confidence": 0.99,
                        "source_page": 1,
                    },
                    {
                        "field_name": "condition",
                        "field_value": "维护状况良好",
                        "confidence": 0.94,
                        "source_page": 4,
                    },
                    {
                        "field_name": "effective_date",
                        "field_value": "2026-01-15",
                        "confidence": 0.97,
                        "source_page": 1,
                    },
                ],
            },
        ],
        "conditions": [
            {
                "description": "放款签约前完成工作及收入核验",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": MARIA_CHEN_ID,
            },
            {
                "description": "补充房屋权属核验材料",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": JAMES_TORRES_ID,
            },
            {
                "description": "完成贷款合同要素确认",
                "severity": ConditionSeverity.PRIOR_TO_FUNDING,
                "status": ConditionStatus.CLEARED,
                "issued_by": MARIA_CHEN_ID,
                "cleared_by": JAMES_TORRES_ID,
            },
            {
                "description": "请补充最新的房屋保险凭证",
                "severity": ConditionSeverity.PRIOR_TO_CLOSING,
                "status": ConditionStatus.OPEN,
                "issued_by": MARIA_CHEN_ID,
            },
        ],
        "decisions": [
            {
                "decision_type": DecisionType.APPROVED,
                "rationale": "申请人还款能力、信用情况及抵押物信息符合演示授信规则，"
                "主要审批条件已满足，具备放款准备条件。",
                "decided_by": MARIA_CHEN_ID,
            },
        ],
        "rate_lock": {
            "locked_rate": 3.100,
            "lock_date": _days_ago(20),
            "expiration_date": _days_from_now(25),
            "is_active": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Historical (closed) loans -- 28 total: 16 approved, 12 denied
# Distributed across 3 loan officers; loan types include all 7 products.
# ---------------------------------------------------------------------------

_HISTORICAL_ADDRESSES = [
    "成都市高新区天府一街演示公馆1栋（虚构地址）",
    "成都市高新区天府二街演示公馆2栋（虚构地址）",
    "成都市锦江区东大街演示花园3栋（虚构地址）",
    "成都市锦江区红星路演示花园4栋（虚构地址）",
    "成都市武侯区人民南路演示雅居5栋（虚构地址）",
    "成都市武侯区武侯大道演示雅居6栋（虚构地址）",
    "成都市青羊区光华大道演示新城7栋（虚构地址）",
    "成都市青羊区日月大道演示新城8栋（虚构地址）",
    "成都市成华区建设路演示家园9栋（虚构地址）",
    "成都市成华区二仙桥路演示家园10栋（虚构地址）",
    "成都市金牛区蜀汉路演示名苑11栋（虚构地址）",
    "成都市金牛区金府路演示名苑12栋（虚构地址）",
    "成都市双流区东升街道演示华庭13栋（虚构地址）",
    "成都市双流区航空港街道演示华庭14栋（虚构地址）",
    "成都市温江区光华大道演示雅苑15栋（虚构地址）",
    "成都市温江区柳城街道演示雅苑16栋（虚构地址）",
    "成都市龙泉驿区驿都大道演示新居17栋（虚构地址）",
    "成都市龙泉驿区大面街道演示新居18栋（虚构地址）",
    "成都市郫都区犀浦街道演示家园19栋（虚构地址）",
    "成都市郫都区红光街道演示家园20栋（虚构地址）",
    "成都市新都区新都街道演示华府21栋（虚构地址）",
    "成都市新都区大丰街道演示华府22栋（虚构地址）",
    "成都市天府新区华阳街道演示公馆23栋（虚构地址）",
    "成都市天府新区正兴街道演示公馆24栋（虚构地址）",
    "成都市青白江区大弯街道演示名邸25栋（虚构地址）",
    "成都市新津区五津街道演示名邸26栋（虚构地址）",
    "成都市都江堰市幸福街道演示家园27栋（虚构地址）",
    "成都市彭州市天彭街道演示家园28栋（虚构地址）",
]

# Borrower refs cycle through the fictional borrowers for historical loans
_HISTORICAL_BORROWER_REFS = [
    MICHAEL_JOHNSON_ID,
    EMILY_RODRIGUEZ_ID,
    ROBERT_KIM_ID,
    LISA_WASHINGTON_ID,
    THOMAS_NGUYEN_ID,
    AMANDA_FOSTER_ID,
    DANIEL_RAMIREZ_ID,
    PATRICIA_CHANG_ID,
]

# Loan officers cycle to give each LO a meaningful historical portfolio
_HISTORICAL_LO_REFS = [
    JAMES_TORRES_ID,
    SARAH_PATEL_ID,
    MARCUS_WILLIAMS_ID,
]

HISTORICAL_LOANS: list[dict] = []

# 16 approved historical loans
for i in range(16):
    _borrower_ref = _HISTORICAL_BORROWER_REFS[i % len(_HISTORICAL_BORROWER_REFS)]
    _lo_ref = _HISTORICAL_LO_REFS[i % len(_HISTORICAL_LO_REFS)]
    _loan_types = [
        LoanType.CONVENTIONAL_30,
        LoanType.CONVENTIONAL_15,
        LoanType.FHA,
        LoanType.VA,
        LoanType.JUMBO,
        LoanType.USDA,
        LoanType.ARM,
    ]
    _created = _days_ago(180 - (i * 10))
    _loan_amount = Decimal(str(2000000 + i * 250000))
    _property_value = _loan_amount + Decimal(str(500000 + i * 50000))
    _credit_scores = [
        720,
        695,
        755,
        710,
        740,
        680,
        760,
        730,
        705,
        750,
        690,
        735,
        745,
        715,
        770,
        725,
    ]

    HISTORICAL_LOANS.append(
        {
            "borrower_ref": _borrower_ref,
            "stage": ApplicationStage.CLOSED,
            "loan_type": _loan_types[i % len(_loan_types)],
            "property_address": _HISTORICAL_ADDRESSES[i],
            "loan_amount": _loan_amount,
            "property_value": _property_value,
            "assigned_to": _lo_ref,
            "created_at": _created,
            "updated_at": _created + timedelta(days=30 + i * 3),
            "financials": {
                "gross_monthly_income": Decimal(str(7000 + i * 500)),
                "monthly_debts": Decimal(str(1800 + i * 100)),
                "total_assets": Decimal(str(50000 + i * 10000)),
                "credit_score": _credit_scores[i],
                "dti_ratio": round(0.25 + (i % 8) * 0.02, 3),
            },
            "documents": [
                {"doc_type": DocumentType.INCOME_CERTIFICATE, "status": DocumentStatus.ACCEPTED},
                {"doc_type": DocumentType.PAY_STUB, "status": DocumentStatus.ACCEPTED},
                {"doc_type": DocumentType.BANK_STATEMENT, "status": DocumentStatus.ACCEPTED},
                {"doc_type": DocumentType.ID_CARD, "status": DocumentStatus.ACCEPTED},
            ],
            "decisions": [
                {
                    "decision_type": DecisionType.APPROVED,
                    "rationale": "申请材料与还款能力符合演示授信规则，审批结论为通过。",
                    "decided_by": MARIA_CHEN_ID,
                    "created_at": _created + timedelta(days=30),
                },
            ],
            "rate_lock": {
                "locked_rate": round(6.5 + (i % 10) * 0.125, 3),
                "lock_date": _created + timedelta(days=20),
                "expiration_date": _created + timedelta(days=65),
                "is_active": False,
            },
        }
    )

# 12 denied historical loans -- spread across 6 months, 3 LOs, all loan types
_DENIAL_RATIONALES = [
    "负债收入比超过演示准入阈值，现有月度偿债压力与家庭收入不匹配。",
    "征信评分未达到当前演示贷款方案的准入要求。",
    "已提供的收入证明不足以支持申请额度。",
    "房产评估价值低于交易价格，贷款成数超过演示方案上限。",
    "近两年工作经历存在较长空档，收入稳定性需要进一步核验。",
    "负债收入比高于当前演示贷款方案的审慎标准。",
    "征信评分未达到现有演示产品的准入要求。",
    "家庭可核验流动资金不足，无法覆盖两个月的预计月供。",
    "房产评估价值低于合同价格，申请人暂无法补足差额。",
    "核验过程中发现未披露负债，重新计算后的负债收入比为52%。",
    "征信评分及近期风险记录未达到演示方案准入要求。",
    "收入证明材料不足，经营性收入暂时无法完成可靠核验。",
]

# Structured denial reasons (JSONB) -- short labels for analytics
_DENIAL_REASON_LABELS: list[list[str]] = [
    ["负债收入比偏高"],
    ["征信评分未达到准入要求"],
    ["收入证明材料不足"],
    ["房产评估价值不足"],
    ["负债收入比偏高"],
    ["征信评分未达到准入要求", "负债收入比偏高"],
    ["收入证明材料不足"],
    ["房产评估价值不足"],
    ["负债收入比偏高"],
    ["征信评分未达到准入要求"],
    ["房产评估价值不足", "负债收入比偏高"],
    ["征信评分未达到准入要求", "收入证明材料不足"],
]

_DENIAL_LOAN_TYPES = [
    LoanType.CONVENTIONAL_30,
    LoanType.FHA,
    LoanType.USDA,
    LoanType.ARM,
    LoanType.CONVENTIONAL_30,
    LoanType.JUMBO,
    LoanType.FHA,
    LoanType.VA,
    LoanType.CONVENTIONAL_15,
    LoanType.ARM,
    LoanType.FHA,
    LoanType.CONVENTIONAL_30,
]

# Spread denials unevenly across 6 months for a realistic trend chart.
# Target month distribution (from today = 2026-03-05):
#   Sep/Oct(1), Nov(1), Dec(3), Jan(3), Feb(2), Mar(2)
# This creates a visible spike in Dec/Jan and a taper toward edges.
_DENIAL_DAYS_AGO = [165, 118, 95, 88, 82, 62, 55, 48, 25, 15, 4, 2]
_DENIED_CREDIT_SCORES = [612, 648, 655, 632, 640, 618, 598, 660, 625, 610, 605, 645]

for i in range(12):
    _borrower_ref = _HISTORICAL_BORROWER_REFS[i % len(_HISTORICAL_BORROWER_REFS)]
    _lo_ref = _HISTORICAL_LO_REFS[i % len(_HISTORICAL_LO_REFS)]
    _idx = 16 + i
    _created = _days_ago(_DENIAL_DAYS_AGO[i])
    _loan_amount = Decimal(str(2500000 + i * 300000))
    _property_value = _loan_amount + Decimal(str(300000 + i * 50000))

    HISTORICAL_LOANS.append(
        {
            "borrower_ref": _borrower_ref,
            "stage": ApplicationStage.DENIED,
            "loan_type": _DENIAL_LOAN_TYPES[i],
            "property_address": _HISTORICAL_ADDRESSES[_idx],
            "loan_amount": _loan_amount,
            "property_value": _property_value,
            "assigned_to": _lo_ref,
            "created_at": _created,
            "updated_at": _created + timedelta(days=20 + i * 3),
            "financials": {
                "gross_monthly_income": Decimal(str(5500 + i * 300)),
                "monthly_debts": Decimal(str(2500 + i * 200)),
                "total_assets": Decimal(str(15000 + i * 5000)),
                "credit_score": _DENIED_CREDIT_SCORES[i],
                "dti_ratio": round(0.42 + i * 0.015, 3),
            },
            "documents": [
                {"doc_type": DocumentType.INCOME_CERTIFICATE, "status": DocumentStatus.ACCEPTED},
                {"doc_type": DocumentType.PAY_STUB, "status": DocumentStatus.ACCEPTED},
                {"doc_type": DocumentType.ID_CARD, "status": DocumentStatus.ACCEPTED},
            ],
            "decisions": [
                {
                    "decision_type": DecisionType.DENIED,
                    "rationale": _DENIAL_RATIONALES[i],
                    "denial_reasons": _DENIAL_REASON_LABELS[i],
                    "decided_by": MARIA_CHEN_ID,
                    "created_at": _created + timedelta(days=25),
                },
            ],
        }
    )


# ---------------------------------------------------------------------------
# HMDA demographics -- one per application (38 total: 10 active + 28 historical)
# ---------------------------------------------------------------------------

# Distribution: ~40% White, ~20% Black, ~15% Hispanic, ~15% Asian, ~10% Other
# Sex: ~50% Male, ~45% Female, ~5% prefer not to say
# These are applied in order to all applications (active first, then historical)

_RACE_DIST = (
    ["White"] * 12
    + ["Black or African American"] * 6
    + ["Asian"] * 5
    + ["Native Hawaiian or Other Pacific Islander"] * 2
    + ["American Indian or Alaska Native"] * 2
    + ["Two or More Races"] * 3
)

_ETHNICITY_DIST = ["Not Hispanic or Latino"] * 26 + ["Hispanic or Latino"] * 4

_SEX_DIST = ["Male"] * 15 + ["Female"] * 14 + ["Prefer not to say"] * 1

_AGE_DIST = ["25-34"] * 9 + ["35-44"] * 11 + ["45-54"] * 6 + ["55-64"] * 4

HMDA_DEMOGRAPHICS: list[dict] = []
for i in range(38):
    HMDA_DEMOGRAPHICS.append(
        {
            "application_index": i,  # resolved at seed time to actual application_id
            "race": _RACE_DIST[i % len(_RACE_DIST)],
            "ethnicity": _ETHNICITY_DIST[i % len(_ETHNICITY_DIST)],
            "sex": _SEX_DIST[i % len(_SEX_DIST)],
            "age": _AGE_DIST[i % len(_AGE_DIST)],
            "collection_method": "self_reported",
        }
    )


# ---------------------------------------------------------------------------
# Credit bureau profiles -- keyed by keycloak user ID
# ---------------------------------------------------------------------------
# Used by the mock credit bureau service to return deterministic data for
# seed borrowers. Each profile corresponds to a borrower in BORROWERS above,
# with credit data consistent with the financials in ACTIVE_APPLICATIONS.

CREDIT_PROFILES: dict[str, dict] = {
    SARAH_MITCHELL_ID: {
        "credit_score": 742,
        "outstanding_accounts": 4,
        "total_outstanding_debt": Decimal("45200.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 12,
    },
    JENNIFER_MITCHELL_ID: {
        "credit_score": 735,
        "outstanding_accounts": 3,
        "total_outstanding_debt": Decimal("38500.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 10,
    },
    EMILY_RODRIGUEZ_ID: {
        "credit_score": 688,
        "outstanding_accounts": 6,
        "total_outstanding_debt": Decimal("67800.00"),
        "derogatory_marks": 1,
        "oldest_account_years": 7,
    },
    MICHAEL_JOHNSON_ID: {
        "credit_score": 765,
        "outstanding_accounts": 5,
        "total_outstanding_debt": Decimal("52000.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 15,
    },
    ROBERT_KIM_ID: {
        "credit_score": 520,
        "outstanding_accounts": 9,
        "total_outstanding_debt": Decimal("92400.00"),
        "derogatory_marks": 4,
        "oldest_account_years": 3,
    },
    LISA_WASHINGTON_ID: {
        "credit_score": 695,
        "outstanding_accounts": 7,
        "total_outstanding_debt": Decimal("71200.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 6,
    },
    THOMAS_NGUYEN_ID: {
        "credit_score": 780,
        "outstanding_accounts": 3,
        "total_outstanding_debt": Decimal("28900.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 18,
    },
    AMANDA_FOSTER_ID: {
        "credit_score": 725,
        "outstanding_accounts": 4,
        "total_outstanding_debt": Decimal("41500.00"),
        "derogatory_marks": 0,
        "oldest_account_years": 9,
    },
    DANIEL_RAMIREZ_ID: {
        "credit_score": 612,
        "outstanding_accounts": 8,
        "total_outstanding_debt": Decimal("89500.00"),
        "derogatory_marks": 3,
        "oldest_account_years": 5,
    },
    PATRICIA_CHANG_ID: {
        "credit_score": 648,
        "outstanding_accounts": 7,
        "total_outstanding_debt": Decimal("78200.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 6,
    },
    DAVID_PARK_ID: {
        "credit_score": 655,
        "outstanding_accounts": 6,
        "total_outstanding_debt": Decimal("72100.00"),
        "derogatory_marks": 2,
        "oldest_account_years": 7,
    },
    MARIA_CHEN_ID: {
        "credit_score": 632,
        "outstanding_accounts": 9,
        "total_outstanding_debt": Decimal("95300.00"),
        "derogatory_marks": 4,
        "oldest_account_years": 4,
    },
}


# ---------------------------------------------------------------------------
# Config hash -- deterministic hash of fixture content for manifest comparison
# ---------------------------------------------------------------------------


def compute_config_hash() -> str:
    """Compute a SHA-256 hash of the fixture data for idempotency checks.

    Hashes the full serialized fixture content so ANY change (new conditions,
    modified fields, reordered records) triggers a re-seed.
    """
    import enum

    def _default(obj: object) -> object:
        if isinstance(obj, enum.Enum):
            return obj.value
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Not serializable: {type(obj)}")

    content = json.dumps(
        {
            "borrowers": BORROWERS,
            "active": ACTIVE_APPLICATIONS,
            "historical": HISTORICAL_LOANS,
            "hmda": HMDA_DEMOGRAPHICS,
        },
        sort_keys=True,
        default=_default,
    )
    return hashlib.sha256(content.encode()).hexdigest()
