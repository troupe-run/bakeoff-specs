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
