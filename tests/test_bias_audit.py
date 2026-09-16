import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from bias_audit import run_four_fifths_audit, FOUR_FIFTHS_THRESHOLD


def make_candidates(group_a_selected, group_a_total, group_b_selected, group_b_total):
    candidates = []
    for i in range(group_a_total):
        candidates.append({"demographic_group": "Group A", "selected": i < group_a_selected})
    for i in range(group_b_total):
        candidates.append({"demographic_group": "Group B", "selected": i < group_b_selected})
    return candidates


def test_equal_selection_rates_pass():
    candidates = make_candidates(5, 10, 5, 10)  # both 50%
    report = run_four_fifths_audit(candidates)
    assert report.passes_four_fifths_rule
    assert report.impact_ratios["Group B"] == pytest.approx(1.0)


def test_below_threshold_is_flagged():
    # Group A: 80% selected, Group B: 40% selected -> ratio 0.5 -> flagged
    candidates = make_candidates(8, 10, 4, 10)
    report = run_four_fifths_audit(candidates)
    assert not report.passes_four_fifths_rule
    assert "Group B" in report.flagged_groups
    assert report.impact_ratios["Group B"] == pytest.approx(0.5)


def test_exactly_at_threshold_passes():
    # Group A: 100% selected, Group B: 80% selected -> ratio exactly 0.8 -> NOT flagged
    candidates = make_candidates(10, 10, 8, 10)
    report = run_four_fifths_audit(candidates)
    assert report.impact_ratios["Group B"] == pytest.approx(FOUR_FIFTHS_THRESHOLD)
    assert "Group B" not in report.flagged_groups


def test_just_below_threshold_is_flagged():
    # ratio of 0.79 should be flagged
    candidates = make_candidates(100, 100, 79, 100)
    report = run_four_fifths_audit(candidates)
    assert "Group B" in report.flagged_groups


def test_three_groups_reference_is_highest_rate():
    candidates = (
        make_candidates(9, 10, 5, 10)  # Group A 90%, Group B 50%
        + [{"demographic_group": "Group C", "selected": True}] * 3
        + [{"demographic_group": "Group C", "selected": False}] * 7  # Group C 30%
    )
    report = run_four_fifths_audit(candidates)
    assert report.reference_group == "Group A"
    assert "Group B" in report.flagged_groups
    assert "Group C" in report.flagged_groups


def test_empty_candidates_raises():
    with pytest.raises(ValueError):
        run_four_fifths_audit([])


def test_no_one_selected_all_pass_trivially():
    candidates = make_candidates(0, 10, 0, 10)
    report = run_four_fifths_audit(candidates)
    assert report.passes_four_fifths_rule
