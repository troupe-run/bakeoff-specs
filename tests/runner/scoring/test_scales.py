import pytest
from runner.scoring import scales


@pytest.mark.parametrize("arm, ctl, want", [(100, 100, 0.5), (1000, 100, 0.0), (10, 100, 1.0),
                                            (5000, 100, 0.0), (200, 100, 0.5 - 0.30103 / 2)])
def test_ratio_score_is_log_scaled_and_capped(arm, ctl, want):
    assert scales.ratio_score(arm, ctl) == pytest.approx(want, abs=1e-4)


@pytest.mark.parametrize("arm, ctl", [(0, 100), (100, 0), (None, 100), (100, None)])
def test_ratio_without_a_positive_pair_is_undefined(arm, ctl):
    assert scales.ratio_score(arm, ctl) is None


def test_churn_zero_against_zero_is_the_midpoint():
    assert scales.churn_score(0, 0, 10.0) == 0.5


def test_per_kloc_normalises_by_lines_and_floors_at_zero():
    assert scales.per_kloc(5, 1000, 10) == pytest.approx(0.5)           # 5 per KLOC of a 10-per-KLOC zero point
    assert scales.per_kloc(5, 2000, 10) == pytest.approx(0.75)          # the same count over twice the code
    assert scales.per_kloc(0, 1000, 10) == 1.0
    assert scales.per_kloc(10, 1000, 10) == 0.0 and scales.per_kloc(500, 1000, 10) == 0.0   # floor, never negative
    assert scales.per_kloc(2.5, 500, 10) == pytest.approx(0.5)          # weighted (fractional) counts


def test_per_kloc_is_unmeasured_without_a_count_or_lines():
    assert scales.per_kloc(None, 1000, 10) is None
    assert scales.per_kloc(3, None, 10) is None and scales.per_kloc(3, 0, 10) is None


def test_lint_weight_counts_a_safe_fix_at_its_weight_and_everything_else_as_one():
    fs = [{"code": "I001", "fix": {"applicability": "safe"}}, {"code": "F401", "fix": {"applicability": "safe"}},
          {"code": "B006", "fix": {"applicability": "unsafe"}}, {"code": "E501", "fix": None},
          {"code": "X", "fix": {"applicability": "displayonly"}}, {"code": "Y"}]
    assert scales.lint_weight(fs, 0.1) == pytest.approx(0.2 + 4)
    assert scales.lint_weight([], 0.1) == 0
    assert scales.lint_weight([{"fix": {"applicability": "safe"}}] * 20, 0.1) == pytest.approx(2.0)


def test_n_a_rating_is_not_a_score_and_1_to_5_spread_evenly():
    assert scales.rating("n/a") is None
    assert [scales.rating(str(n)) for n in range(1, 6)] == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_churn_proves_add_one():
    """churn_score(0, 9) = ratio_score(1, 10) = 1.0; ratio_score(0, 9) would be None without add-one."""
    assert scales.churn_score(0, 9) == 1.0
    assert scales.ratio_score(0, 9) is None


def test_ratio_better_side_past_cap():
    """ratio_score(1, 1000) = 1.0 (100x better than cap of 10x, capped at 1.0)"""
    assert scales.ratio_score(1, 1000) == 1.0


def test_ratio_negative_input_is_undefined():
    """Negative inputs should return None"""
    assert scales.ratio_score(-1, 100) is None
    assert scales.ratio_score(100, -1) is None


def test_rating_table_maps_scales_to_rating_keys():
    table = scales.rating_table({"rating_1": 0.1, "rating_5": 0.9, "ratio_cap": 10.0})
    assert table == {"1": 0.1, "2": 0.25, "3": 0.5, "4": 0.75, "5": 0.9}       # an absent key keeps its default


def test_rating_with_custom_table():
    """rating() can use a custom table passed from weights.toml"""
    custom_table = {"1": 0.1, "3": 0.5, "5": 0.9}
    assert scales.rating("3", table=custom_table) == 0.5
    assert scales.rating("5", table=custom_table) == 0.9


def test_a_half_step_scores_midway_and_off_scale_values_do_not_score():
    assert scales.rating("3.5") == 0.625 and scales.rating("1.5") == 0.125
    assert scales.rating("5.5") is None and scales.rating("0.5") is None and scales.rating("6") is None
    assert scales.rating("nan") is None and scales.rating("inf") is None and scales.rating("") is None


def test_a_reslice_mean_between_whole_ratings_scores_linearly_between_them():
    assert scales.rating("4.25") == 0.8125 and scales.rating("5.0") == 1.0 and scales.rating("1.0") == 0.0
    custom = {"1": 0.1, "2": 0.3, "3": 0.5, "4": 0.7, "5": 0.9}
    assert abs(scales.rating("3.25", custom) - 0.55) < 1e-9
