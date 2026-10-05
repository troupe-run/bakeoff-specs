from runner.scoring import regressions as r


def test_a_test_that_passed_before_and_fails_now_is_a_regression():
    out = r.compute({"t1": "passed", "t2": "passed"}, {"t1": "failed", "t2": "passed", "t3": "failed"}, frozenset())
    assert out["regressed"] == ["t1"] and out["rate"] == 0.5


def test_new_tests_and_tests_failing_before_are_not_regressions():
    out = r.compute({"t1": "failed"}, {"t1": "failed", "t2": "failed"}, frozenset())
    assert out["regressed"] == [] and out["rate"] is None and out["earlier_total"] == 1 and out["earlier_passing_before"] == 0


def test_excluded_tests_drop_out_of_both_sides():
    out = r.compute({"t1": "passed"}, {"t1": "failed"}, frozenset({"t1"}))
    assert out["regressed"] == [] and out["earlier_total"] == 0


def test_step_one_has_no_earlier_tests():
    assert r.compute(None, {"t1": "passed"}, frozenset())["rate"] is None


def test_retired_tests_are_not_regressions():
    out = r.compute({"t1": "passed"}, {"t2": "passed"}, frozenset())
    assert out["retired"] == ["t1"] and out["regressed"] == [] and out["rate"] is None


def test_skipped_status_counts_as_regression():
    out = r.compute({"t1": "passed"}, {"t1": "skipped"}, frozenset())
    assert out["regressed"] == ["t1"] and out["rate"] == 0.0
