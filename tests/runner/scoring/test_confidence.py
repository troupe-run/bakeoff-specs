import pytest
from runner.scoring import confidence

W = {"a": 50.0, "b": 50.0}
PW = {}


def arm(fa, fb, lenses=None):
    step = {"score": fa, "disputed": lenses is not None, "lenses": lenses or {}}
    return {"dimensions": {
        "a": {"score": 50 * fa, "max": 50, "parts": {"a": {"score": fa, "steps": {"1": step}}}},
        "b": {"score": 50 * fb, "max": 50, "parts": {"b": {"score": fb, "steps": {"1": {"score": fb}}}}}}}


def test_weight_variants_keep_the_sum_at_100():
    vs = confidence.weight_variants(W)
    assert vs[0][0] == "base" and all(sum(v.values()) == pytest.approx(100) for _, v in vs) and len(vs) == 5


def test_low_and_high_use_the_extreme_lens_of_disputed_items():
    a = arm(0.5, 1.0, lenses={"x": 0, "y": 2, "z": 4})
    assert confidence.total(a, W, PW, "low") == pytest.approx(50)
    assert confidence.total(a, W, PW, "high") == pytest.approx(100)


def test_close_arms_with_a_disputed_item_are_within_noise():
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {"p": arm(0.6, 0.6, lenses={"x": 1, "y": 3, "z": 3}), "q": arm(0.58, 0.6), "r": arm(0.1, 0.1)}}
    out = confidence.check(s)
    assert out["ranking"] == ["p", "q", "r"] and out["groups"] == [["p", "q"], ["r"]]


def test_far_apart_arms_are_ranked():
    s = {"weights": {"dimensions": W, "parts": PW}, "arms": {"p": arm(0.9, 0.9), "q": arm(0.2, 0.2)}}
    assert confidence.check(s)["groups"] == [["p"], ["q"]]
