# This project was developed with assistance from AI tools.
"""Tests for the disclosure acknowledgment service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.disclosure import (
    _DISCLOSURE_IDS,
    DISCLOSURE_BY_ID,
    REQUIRED_DISCLOSURES,
    get_disclosure_status,
    record_disclosure_acknowledgment,
)

# ---------------------------------------------------------------------------
# REQUIRED_DISCLOSURES config
# ---------------------------------------------------------------------------


def test_required_disclosures_has_four_entries():
    assert len(REQUIRED_DISCLOSURES) == 4


def test_required_disclosures_ids():
    expected = {"loan_estimate", "privacy_notice", "hmda_notice", "equal_opportunity_notice"}
    assert _DISCLOSURE_IDS == expected


def test_disclosure_by_id_maps_all():
    assert set(DISCLOSURE_BY_ID.keys()) == _DISCLOSURE_IDS
    for d_id, d_info in DISCLOSURE_BY_ID.items():
        assert d_info["id"] == d_id
        assert "label" in d_info
        assert "summary" in d_info


# ---------------------------------------------------------------------------
# get_disclosure_status
# ---------------------------------------------------------------------------


def _mock_audit_event(disclosure_id: str, application_id: int = 1):
    """Create a mock AuditEvent for a disclosure acknowledgment."""
    event = MagicMock()
    event.event_type = "disclosure_acknowledged"
    event.application_id = application_id
    event.event_data = {
        "disclosure_id": disclosure_id,
        "disclosure_label": DISCLOSURE_BY_ID[disclosure_id]["label"],
        "borrower_confirmation": "I acknowledge",
    }
    return event


@pytest.mark.asyncio
async def test_status_all_pending():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute.return_value = result_mock

    result = await get_disclosure_status(session, application_id=1)

    assert result["application_id"] == 1
    assert result["all_acknowledged"] is False
    assert result["acknowledged"] == []
    assert len(result["pending"]) == 4


@pytest.mark.asyncio
async def test_status_all_acknowledged():
    events = [
        _mock_audit_event("loan_estimate"),
        _mock_audit_event("privacy_notice"),
        _mock_audit_event("hmda_notice"),
        _mock_audit_event("equal_opportunity_notice"),
    ]

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = events
    session.execute.return_value = result_mock

    result = await get_disclosure_status(session, application_id=1)

    assert result["all_acknowledged"] is True
    assert len(result["acknowledged"]) == 4
    assert result["pending"] == []


@pytest.mark.asyncio
async def test_status_partial_acknowledgment():
    events = [
        _mock_audit_event("loan_estimate"),
        _mock_audit_event("hmda_notice"),
    ]

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = events
    session.execute.return_value = result_mock

    result = await get_disclosure_status(session, application_id=1)

    assert result["all_acknowledged"] is False
    assert sorted(result["acknowledged"]) == ["hmda_notice", "loan_estimate"]
    assert sorted(result["pending"]) == ["equal_opportunity_notice", "privacy_notice"]


@pytest.mark.asyncio
async def test_status_ignores_unknown_disclosure_ids():
    """An event with an unrecognized disclosure_id should be ignored."""
    event = MagicMock()
    event.event_data = {"disclosure_id": "unknown_thing"}

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [event]
    session.execute.return_value = result_mock

    result = await get_disclosure_status(session, application_id=1)

    assert result["all_acknowledged"] is False
    assert result["acknowledged"] == []
    assert len(result["pending"]) == 4


@pytest.mark.asyncio
async def test_status_deduplicates_repeated_acknowledgments():
    """If the same disclosure is acknowledged twice, it counts once."""
    events = [
        _mock_audit_event("loan_estimate"),
        _mock_audit_event("loan_estimate"),
    ]

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = events
    session.execute.return_value = result_mock

    result = await get_disclosure_status(session, application_id=1)

    assert result["acknowledged"] == ["loan_estimate"]
    assert len(result["pending"]) == 3


@pytest.mark.asyncio
@patch("src.services.disclosure.write_audit_event", new_callable=AsyncMock)
async def test_record_acknowledgment_writes_audit_event(mock_write_audit):
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute.return_value = result_mock
    user = MagicMock()
    user.user_id = "borrower-1"
    user.role.value = "borrower"

    result = await record_disclosure_acknowledgment(
        session,
        user,
        application_id=1,
        disclosure_id="privacy_notice",
        borrower_confirmation="我已阅读并确认",
    )

    assert result == DISCLOSURE_BY_ID["privacy_notice"]
    mock_write_audit.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.disclosure.write_audit_event", new_callable=AsyncMock)
async def test_record_acknowledgment_is_idempotent(mock_write_audit):
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [_mock_audit_event("privacy_notice")]
    session.execute.return_value = result_mock
    user = MagicMock()
    user.user_id = "borrower-1"
    user.role.value = "borrower"

    result = await record_disclosure_acknowledgment(
        session,
        user,
        application_id=1,
        disclosure_id="privacy_notice",
        borrower_confirmation="我已阅读并确认",
    )

    assert result == DISCLOSURE_BY_ID["privacy_notice"]
    mock_write_audit.assert_not_awaited()
    session.commit.assert_not_awaited()
