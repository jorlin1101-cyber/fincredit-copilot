# This project was developed with assistance from AI tools.
"""Deterministic normalization for source-grounded lending document fields."""

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "贰": 2,
    "两": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}
_SMALL_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
_LARGE_UNITS = {"万": 10_000, "萬": 10_000, "亿": 100_000_000, "億": 100_000_000}
_DATE_RE = re.compile(
    r"(?P<year>\d{4})\s*[年./-]\s*(?P<month>\d{1,2})\s*[月./-]\s*(?P<day>\d{1,2})\s*日?"
)
_NUMBER_RE = re.compile(r"[-+]?\d[\d,，\s]*(?:\.\d+)?")


def normalize_name(value: str) -> str:
    """Normalize width, whitespace, Latin case, and common middle-dot variants."""
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = normalized.replace("•", "·").replace("・", "·")
    return re.sub(r"\s+", "", normalized).casefold()


def normalize_date(value: str) -> str | None:
    """Normalize common Chinese and numeric dates to ISO-8601."""
    normalized = unicodedata.normalize("NFKC", value).strip()
    match = _DATE_RE.search(normalized)
    if match:
        try:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            ).isoformat()
        except ValueError:
            return None

    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
        except ValueError:
            return None
    return None


def _parse_chinese_integer(value: str) -> int | None:
    total = 0
    section = 0
    number = 0
    saw_number = False
    for char in value:
        if char in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[char]
            saw_number = True
        elif char in _SMALL_UNITS:
            section += (number or 1) * _SMALL_UNITS[char]
            number = 0
            saw_number = True
        elif char in _LARGE_UNITS:
            section += number
            total += (section or 1) * _LARGE_UNITS[char]
            section = 0
            number = 0
            saw_number = True
    return total + section + number if saw_number else None


def normalize_amount(value: str) -> str | None:
    """Normalize Arabic or uppercase-Chinese yuan amounts to two decimals."""
    normalized = unicodedata.normalize("NFKC", value).strip()
    number_match = _NUMBER_RE.search(normalized)
    if number_match:
        numeric = re.sub(r"[,，\s]", "", number_match.group())
        try:
            return f"{Decimal(numeric):.2f}"
        except InvalidOperation:
            return None

    chinese = re.sub(r"[人民币圆元整正\s]", "", normalized)
    integer_text, _, fractional_text = chinese.partition("角")
    fen_digit = None
    if "分" in fractional_text:
        fen_text = fractional_text.split("分", 1)[0]
        fen_digit = _CHINESE_DIGITS.get(fen_text[-1:])
    jiao_digit = _CHINESE_DIGITS.get(integer_text[-1:]) if "角" in chinese else None
    if "角" in chinese and jiao_digit is not None:
        integer_text = integer_text[:-1]

    integer = _parse_chinese_integer(integer_text)
    if integer is None:
        return None
    amount = Decimal(integer)
    if jiao_digit is not None:
        amount += Decimal(jiao_digit) / 10
    if fen_digit is not None:
        amount += Decimal(fen_digit) / 100
    return f"{amount:.2f}"


def normalize_account(value: str, *, last4_only: bool = False) -> str | None:
    """Normalize masked/full account identifiers without unmasking data."""
    normalized = unicodedata.normalize("NFKC", value).upper()
    compact = re.sub(r"[^0-9X*]", "", normalized)
    digits = re.sub(r"\D", "", compact)
    if last4_only:
        return digits[-4:] if len(digits) >= 4 else None
    return compact or None


def normalize_extracted_value(field_name: str, value: str | None) -> str | None:
    """Dispatch normalization based on an explicit schema field name."""
    if value is None:
        return None
    name = field_name.strip().lower()
    if "account_number_last4" in name or name.endswith("last4"):
        return normalize_account(value, last4_only=True)
    if "id_number" in name or "account_number" in name:
        return normalize_account(value)
    if any(
        token in name
        for token in ("date", "valid_from", "valid_until", "period_start", "period_end")
    ):
        return normalize_date(value)
    if any(
        token in name
        for token in (
            "income",
            "balance",
            "amount",
            "wages",
            "gross_pay",
            "net_pay",
            "purchase_price",
            "salary_credit",
        )
    ):
        return normalize_amount(value)
    if "name" in name or name in {"account_holder", "employee", "borrower"}:
        return normalize_name(value)
    return unicodedata.normalize("NFKC", value).strip()
