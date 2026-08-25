# This project was developed with assistance from AI tools.
"""Integrity checks for the shared A/B/C policy evaluation dataset."""

import json
from collections import Counter
from pathlib import Path


def test_policy_pilot_has_frozen_30_case_distribution():
    path = (
        Path(__file__).resolve().parents[3]
        / "evaluations"
        / "datasets"
        / "fincredit_policy_pilot.json"
    )
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) == 30
    assert len({case["id"] for case in cases}) == 30
    assert Counter(case["category"] for case in cases) == {
        "simple_fact": 10,
        "cross_passage": 10,
        "expired_or_conflict": 5,
        "no_answer": 5,
    }
    assert all(case["expected_sources"] or not case["should_answer"] for case in cases)
