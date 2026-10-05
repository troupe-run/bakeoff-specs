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


def test_deduction_floors_at_zero_and_passes_none_through():
    assert scales.deduction(7, 0.05) == pytest.approx(0.65) and scales.deduction(40, 0.05) == 0.0
    assert scales.deduction(None, 0.05) is None


def test_out_of_scope_rating_is_not_a_score():
    assert scales.rating("out_of_scope") is None and scales.rating("acceptable") == 0.67


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
    scales_dict = {"rating_good": 1.0, "rating_acceptable": 0.67, "rating_poor": 0.0}
    table = scales.rating_table(scales_dict)
    assert table == {"good": 1.0, "acceptable": 0.67, "poor": 0.0}


def test_rating_with_custom_table():
    """rating() can use a custom table passed from weights.toml"""
    custom_table = {"good": 0.9, "acceptable": 0.5, "poor": 0.1}
    assert scales.rating("acceptable", table=custom_table) == 0.5
    assert scales.rating("good", table=custom_table) == 0.9
