# This project was developed with assistance from AI tools.
"""Deterministic normalization tests for Chinese lending fields."""

import pytest

from src.services.extraction_normalization import (
    normalize_account,
    normalize_amount,
    normalize_date,
    normalize_extracted_value,
    normalize_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("人民币20,000元", "20000.00"),
        ("人民币贰万元整", "20000.00"),
        ("壹万贰仟叁佰肆拾伍元陆角柒分", "12345.67"),
    ],
)
def test_normalize_amount(raw, expected):
    assert normalize_amount(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026年8月5日", "2026-08-05"),
        ("2026/08/05", "2026-08-05"),
        ("20260805", "2026-08-05"),
    ],
)
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_invalid_date_returns_none():
    assert normalize_date("2026年2月30日") is None


def test_normalize_name_removes_width_and_spaces():
    assert normalize_name(" Ｚｈａｎｇ · 晨 ") == "zhang·晨"


def test_normalize_masked_account_and_last_four():
    assert normalize_account("账号 **** **** 6688") == "********6688"
    assert normalize_account("尾号 6688", last4_only=True) == "6688"


def test_field_dispatch_is_deterministic():
    assert normalize_extracted_value("monthly_gross_income", "20,000元") == "20000.00"
    assert normalize_extracted_value("issue_date", "2026.8.5") == "2026-08-05"
    assert normalize_extracted_value("employee_name", " 张 晨 ") == "张晨"
