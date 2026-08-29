# This project was developed with assistance from AI tools.
"""Field-level validation for mortgage application intake.

Pure functions that validate and normalize individual field values
collected during conversational intake.
"""

import re
from collections.abc import Callable
from datetime import date, datetime


def validate_id_number(value: str) -> tuple[bool, str, str | None]:
    """Validate an 18-character Chinese resident identity-card number."""
    normalized = re.sub(r"\s", "", value.strip()).upper()
    if not re.fullmatch(r"\d{17}[\dX]", normalized):
        return False, "居民身份证号码应为18位，末位可以是数字或X", None

    try:
        birth_date = datetime.strptime(normalized[6:14], "%Y%m%d").date()
    except ValueError:
        return False, "居民身份证号码中的出生日期无效", None
    if birth_date >= date.today():
        return False, "居民身份证号码中的出生日期无效", None

    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    expected = checks[sum(int(n) * w for n, w in zip(normalized[:17], weights, strict=True)) % 11]
    if normalized[-1] != expected:
        return False, "居民身份证号码校验位不正确", None
    return True, "", normalized


def validate_ssn(value: str) -> tuple[bool, str, str | None]:
    """Backward-compatible alias for the former database field name."""
    return validate_id_number(value)


def validate_dob(value: str) -> tuple[bool, str, str | None]:
    """Validate date of birth. Accepts multiple formats."""
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
    parsed: date | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(value.strip(), fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return False, "无法识别出生日期，请使用 YYYY-MM-DD 格式", None

    today = date.today()
    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    if age < 18:
        return False, "申请人须年满18周岁", None
    if age > 120:
        return False, "出生日期无效", None
    return True, "", parsed.isoformat()


def validate_email(value: str) -> tuple[bool, str, str | None]:
    """Basic email format validation."""
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return False, "电子邮箱格式无效", None
    return True, "", value


def validate_income(value: str) -> tuple[bool, str, str | None]:
    """Validate gross monthly income."""
    cleaned = re.sub(r"[$¥￥,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "无法识别月收入金额", None
    if amount < 0:
        return False, "月收入不能为负数", None
    if amount > 4_200_000:
        return False, "月收入金额异常，请核对后重新提交", None
    return True, "", f"{amount:.2f}"


def validate_monthly_debts(value: str) -> tuple[bool, str, str | None]:
    """Validate monthly debt obligations."""
    cleaned = re.sub(r"[$¥￥,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "无法识别每月负债金额", None
    if amount < 0:
        return False, "每月负债不能为负数", None
    return True, "", f"{amount:.2f}"


def validate_total_assets(value: str) -> tuple[bool, str, str | None]:
    """Validate total assets."""
    cleaned = re.sub(r"[$¥￥,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "无法识别资产金额", None
    if amount < 0:
        return False, "资产金额不能为负数", None
    return True, "", f"{amount:.2f}"


def validate_loan_amount(value: str) -> tuple[bool, str, str | None]:
    """Validate requested loan amount."""
    cleaned = re.sub(r"[$¥￥,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "无法识别贷款金额", None
    if amount <= 0:
        return False, "贷款金额必须大于0", None
    if amount > 100_000_000:
        return False, "贷款金额超过演示系统支持的上限", None
    return True, "", f"{amount:.2f}"


def validate_property_value(value: str) -> tuple[bool, str, str | None]:
    """Validate property value."""
    cleaned = re.sub(r"[$¥￥,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "无法识别房产价值", None
    if amount <= 0:
        return False, "房产价值必须大于0", None
    return True, "", f"{amount:.2f}"


def validate_credit_score(value: str) -> tuple[bool, str, str | None]:
    """Validate credit score (300-850)."""
    cleaned = value.strip()
    try:
        score = int(cleaned)
    except ValueError:
        return False, "模拟征信评分必须是数字", None
    if score < 300 or score > 850:
        return False, "模拟征信评分须在300至850之间", None
    return True, "", str(score)


def validate_loan_type(value: str) -> tuple[bool, str, str | None]:
    """Validate loan type against known types."""
    from db.enums import LoanType

    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    # Common aliases
    aliases = {
        "conventional": "conventional_30",
        "conv_30": "conventional_30",
        "conv_15": "conventional_15",
        "30_year": "conventional_30",
        "15_year": "conventional_15",
        "adjustable": "arm",
        "adjustable_rate": "arm",
        "variable_rate": "arm",
        "商业住房贷款": "conventional_30",
        "公积金贷款": "fha",
        "组合贷款": "va",
        "lpr浮动利率": "arm",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        LoanType(normalized)
        return True, "", normalized
    except ValueError:
        valid = [lt.value for lt in LoanType]
        return False, f"无法识别贷款类型，可用内部代码：{'、'.join(valid)}", None


def validate_employment_status(value: str) -> tuple[bool, str, str | None]:
    """Validate employment status."""
    from db.enums import EmploymentStatus

    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "employed": "w2_employee",
        "w2": "w2_employee",
        "self": "self_employed",
        "freelance": "self_employed",
        "contractor": "self_employed",
        "1099": "self_employed",
        "工薪就业": "w2_employee",
        "自主经营": "self_employed",
        "退休": "retired",
        "待业": "unemployed",
        "其他": "other",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        EmploymentStatus(normalized)
        return True, "", normalized
    except ValueError:
        valid = [es.value for es in EmploymentStatus]
        return False, f"无法识别就业状态，可用内部代码：{'、'.join(valid)}", None


_VALIDATORS: dict[str, Callable] = {
    "id_number": validate_id_number,
    "ssn": validate_ssn,
    "date_of_birth": validate_dob,
    "email": validate_email,
    "gross_monthly_income": validate_income,
    "monthly_debts": validate_monthly_debts,
    "total_assets": validate_total_assets,
    "loan_amount": validate_loan_amount,
    "property_value": validate_property_value,
    "credit_score": validate_credit_score,
    "loan_type": validate_loan_type,
    "employment_status": validate_employment_status,
}


def validate_field(field_name: str, value: str) -> tuple[bool, str, str | None]:
    """Validate a single field by name.

    Returns (is_valid, error_message, normalized_value).
    Fields without a dedicated validator pass through as-is.
    """
    validator = _VALIDATORS.get(field_name)
    if validator is None:
        return True, "", value.strip() if isinstance(value, str) else value
    return validator(str(value))
