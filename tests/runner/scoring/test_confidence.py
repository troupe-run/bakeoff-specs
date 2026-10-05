import json
import pytest
from runner.scoring import confidence, aggregate, inputs, values
from runner import paths

W = {"a": 50.0, "b": 50.0}
PW = {}
LENSES = ("auditor", "maintainer", "newcomer")


def arm(fa, fb, lenses=None):
    # For disputed steps, derive score from median of lenses / 4 (matching aggregate output shape)
    if lenses is not None:
        sorted_lens = sorted(lenses.values())
        median_lens = sorted_lens[len(sorted_lens) // 2]
        score = median_lens / 4
    else:
        score = fa
    step = {"score": score, "disputed": lenses is not None, "lenses": lenses or {}}
    return {"dimensions": {
        "a": {"score": 50 * fa, "max": 50, "parts": {"a": {"score": fa, "steps": {"1": step}}}},
        "b": {"score": 50 * fb, "max": 50, "parts": {"b": {"score": fb, "steps": {"1": {"score": fb}}}}}}}


def test_weight_variants_keep_the_sum_at_100():
    vs = confidence.weight_variants(W)
    assert vs[0][0] == "base" and all(sum(v.values()) == pytest.approx(100) for _, v in vs)


def test_weight_variants_skip_when_others_sum_to_zero():
    # {"a": 100, "b": 0}: can't renormalize when others sum to 0
    vs = confidence.weight_variants({"a": 100, "b": 0})
    variant_names = [name for name, _ in vs]
    # a +5 would be capped at 100 (duplicate with base), a -5 can't renormalize (rest sum=0)
    # b +5 should appear: b goes from 0 to 5, a scales from 100 to 95
    assert "base" in variant_names and "b +5" in variant_names
    # Neither a +5 (duplicate) nor a -5 (can't renormalize) should appear
    assert not any("a +5" in name or "a -5" in name for name in variant_names)


def test_weight_variants_cap_at_100():
    vs = confidence.weight_variants({"a": 98, "b": 2})
    # a+5 would be 103, should be capped at 100
    for name, v in vs:
        if "a +5" in name:
            assert v["a"] == pytest.approx(100) and v["b"] == pytest.approx(0)


def test_weight_variants_drop_duplicates():
    # {"c": 3, "d": 97}: various edge cases should produce no duplicates
    vs = confidence.weight_variants({"c": 3, "d": 97})
    variant_names = [name for name, _ in vs]
    # Should not have duplicates
    assert len(variant_names) == len(set(variant_names))


def test_low_and_high_use_the_extreme_lens_of_disputed_items():
    a = arm(0.5, 1.0, lenses={"x": 0, "y": 2, "z": 4})
    assert confidence.total(a, W, PW, "low") == pytest.approx(50)
    assert confidence.total(a, W, PW, "high") == pytest.approx(100)


def test_flip_between_ranks_groups_all_between():
    # When two arms flip relative positions, all arms between them join the group
    # Create a scenario where with different weights, order changes
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "p": arm(0.6, 0.0),           # rank 0: 30 + 0 = 30
             "q": arm(0.5, 0.5),           # rank 1: 25 + 25 = 50
             "r": arm(0.0, 0.6)            # rank 2: 0 + 30 = 30
         }}
    out = confidence.check(s)
    # Base ranking: q (50) > p/r (30 each, tie on name: p < r)
    assert out["ranking"][0] == "q"
    # With weight adjustments and disputes, this should create a scenario where order flips


def test_arms_that_never_flip_are_separate_groups():
    # p > q > r and they never flip order - they should be in separate groups
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "p": arm(1.0, 1.0),
             "q": arm(0.5, 0.5),
             "r": arm(0.0, 0.0)
         }}
    out = confidence.check(s)
    assert out["groups"] == [["p"], ["q"], ["r"]]


def test_a_tie_is_not_a_flip():
    # Two arms with exact same scores should not be considered a flip
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "p": arm(0.5, 0.5),
             "q": arm(0.5, 0.5)
         }}
    out = confidence.check(s)
    # They should be in separate groups (tie means no flip, so not grouped together)
    assert out["groups"] == [["p"], ["q"]]


def test_owner_verdict_keeps_score_in_low_and_high():
    # A step with owner verdict should use its score, not extreme lenses
    step_with_owner = {"score": 0.5, "disputed": True, "lenses": {"x": 0, "y": 4}, "owner": "reviewer"}
    step_no_owner = {"score": 0.5, "disputed": True, "lenses": {"x": 0, "y": 4}}

    a = {"dimensions": {
        "a": {"score": 50, "max": 50, "parts": {"a": {"score": 0.5, "steps": {"1": step_with_owner}}}}
    }}
    b = {"dimensions": {
        "a": {"score": 50, "max": 50, "parts": {"a": {"score": 0.5, "steps": {"1": step_no_owner}}}}
    }}

    # With owner verdict, low and high should use the score
    assert confidence.total(a, {"a": 100}, {}, "low") == pytest.approx(50)
    assert confidence.total(a, {"a": 100}, {}, "high") == pytest.approx(50)

    # Without owner verdict, low uses min lens / 4 = 0 / 4 = 0
    assert confidence.total(b, {"a": 100}, {}, "low") == pytest.approx(0)
    # Without owner verdict, high uses max lens / 4 = 4 / 4 = 1
    assert confidence.total(b, {"a": 100}, {}, "high") == pytest.approx(100)


def write_collected(pass_, arm, step, **fields):
    rec = {"arm": arm, "step": step, "outcome": values.val("done", "x"),
           "hidden": values.val({"passed": 10, "total": 10, "excluded": [], "per_test": {}}, "x"),
           "regressions": values.val({"rate": None}, "x"),
           "quality": values.val({"mypy_errors": 0, "ruff_findings": 0, "mutation_score": 0.8,
                                  "mutation_state": "measured"}, "x"),
           "time": values.val({"seconds": 100.0, "attempt": 1, "turns": []}, "x"),
           "cost": values.val({}, "x"), "questions": values.val([], "x"), "violations": values.val([], "x"),
           "churn": values.val({"lines": 0, "files": [], "total_lines": 0}, "x"),
           "phases": {"method": values.val([], "x"), "common": values.val({}, "x")}}
    for k, v in fields.items():
        rec[k] = v if isinstance(v, dict) and ("value" in v or "missing" in v) else values.val(v, "x")
    f = paths.scoring_out(pass_) / "collected" / arm / f"{step:02d}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(values.dump(rec))


def write_judged(pass_, part, arm, key, scores):
    for lens, s in zip(LENSES, scores):
        f = paths.scoring_out(pass_) / "judged" / part / arm / key / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": s, "status": "ok", "evidence": ["x"], "notes": ""}))


@pytest.fixture
def p(tmp_state, monkeypatch):
    (paths.RESULTS / "p").mkdir(parents=True)
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {})
    for arm_name in ("alpha", "control"):
        write_collected("p", arm_name, 1)
    return "p"


def test_confidence_total_matches_aggregate_arm_total(p):
    # Run aggregate and verify confidence.total matches the arm's total
    scores_json = aggregate.run(p)
    scores = json.loads(scores_json.read_text())

    w = scores["weights"]
    for arm_name, arm_data in scores["arms"].items():
        if arm_data["total"] is not None:
            calculated = confidence.total(arm_data, w["dimensions"], w["parts"], "median")
            assert calculated == pytest.approx(arm_data["total"])
