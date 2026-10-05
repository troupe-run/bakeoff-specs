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
    # With {"a": 98, "b": 2}, a+5 would be 103 but should be capped at 100
    vs = confidence.weight_variants({"a": 98, "b": 2})
    variant_names = [name for name, _ in vs]
    # Assert "a +5" exists (test must fail if cap logic is missing)
    assert "a +5" in variant_names
    # Find and verify the capped variant
    a_plus_5 = next((v for name, v in vs if name == "a +5"), None)
    assert a_plus_5 is not None
    assert a_plus_5["a"] == pytest.approx(100) and a_plus_5["b"] == pytest.approx(0)


def test_weight_variants_drop_duplicates():
    # With {"c": 3, "d": 97}, c-5 gives (c=0, d=100) and d+5 caps to (d=100, c=0)
    # These are identical, so exactly one should be present (not both)
    vs = confidence.weight_variants({"c": 3, "d": 97})
    variant_names = [name for name, _ in vs]
    variant_dicts = [v for _, v in vs]

    # Assert exactly one of "c -5" or "d +5" is present (not both, not neither)
    c_minus_5_present = "c -5" in variant_names
    d_plus_5_present = "d +5" in variant_names
    assert c_minus_5_present != d_plus_5_present, "Exactly one of 'c -5'/'d +5' should be present (they're duplicates)"

    # All returned weight dicts should be distinct
    for i, v1 in enumerate(variant_dicts):
        for j, v2 in enumerate(variant_dicts):
            if i != j:
                assert v1 != v2, f"Duplicate weight dicts found at indices {i} and {j}"


def test_low_and_high_use_the_extreme_lens_of_disputed_items():
    a = arm(0.5, 1.0, lenses={"x": 0, "y": 2, "z": 4})
    assert confidence.total(a, W, PW, "low") == pytest.approx(50)
    assert confidence.total(a, W, PW, "high") == pytest.approx(100)


def test_flip_between_ranks_1_and_3_groups_all_three():
    # A flip between ranks 1 and 3 groups all three arms
    # q = (0.0, 1.02): base = 0*50 + 1.02*50 = 51
    # p = (1.0, 0.01): base = 1.0*50 + 0.01*50 = 50.5
    # r = (0.5, 0.5): base = 0.5*50 + 0.5*50 = 50 (always 50)
    # Base ranking: [q (51), p (50.5), r (50)]
    # Under "a +5" (a=55, b=45): q=0*55+1.02*45=45.9, p=1*55+0.01*45=55.45, r=50
    # New ranking under a+5: [p (55.45), r (50), q (45.9)] - q flipped from rank 0 to 2
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "q": arm(0.0, 1.02),
             "p": arm(1.0, 0.01),
             "r": arm(0.5, 0.5)
         }}
    out = confidence.check(s)
    assert out["ranking"] == ["q", "p", "r"]
    # q flips from rank 0 to rank 2, so all three group together
    assert out["groups"] == [["q", "p", "r"]]
    # order_changes must be non-empty (at least one variant causes a flip)
    assert len(out["order_changes"]) > 0


def test_overlapping_intervals_without_flip_stay_separate():
    # Overlapping intervals without a flip stay separate groups
    # t = (1.0, 0.0): varies with a's weight = 1.0*a + 0.0*b = a (ranges 45 to 55)
    # s = (1.0, 0.04): always = 1.0*a + 0.04*b = a + 0.04*b (always ahead by ≥1.8)
    # Base: s = 1.0*50 + 0.04*50 = 52, t = 1.0*50 + 0.0*50 = 50
    # Base ranking: [s (52), t (50)]
    # Under "a -5" (a=45, b=55): s = 1.0*45 + 0.04*55 = 47.2, t = 45, s still ahead
    # Under "a +5" (a=55, b=45): s = 1.0*55 + 0.04*45 = 56.8, t = 55, s still ahead
    # Intervals: s=[47.2, 56.8], t=[45, 55]. s_lo=47.2 < t_hi=55, so they overlap.
    # But s never flips with t, so they're separate groups.
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "s": arm(1.0, 0.04),
             "t": arm(1.0, 0.0)
         }}
    out = confidence.check(s)
    assert out["ranking"] == ["s", "t"]
    # Intervals overlap: s_lo < t_hi
    assert out["intervals"]["s"][0] < out["intervals"]["t"][1]
    # But no order_changes (they never flip)
    assert len(out["order_changes"]) == 0
    # And they remain separate groups (no flip means no grouping)
    assert out["groups"] == [["s"], ["t"]]


def test_near_tie_within_check_tolerance_records_no_change():
    # u = (0.5 + 1e-12, 0.5), v = (0.5, 0.5 + 1e-12); u - v = 1e-12 * (w_a - w_b)
    # Base (a=50, b=50): u - v = 0, so u ranks first by name.
    # "a +5": u - v = +1e-11; "a -5": u - v = -1e-11, i.e. v ahead by 1e-11 < CHECK_TOL (1e-9).
    # With CHECK_TOL = 0 the "a -5" variants would be recorded as changes and u, v grouped;
    # this test fails in that case (evidence in the task 12 report, fix round 4).
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {
             "u": arm(0.5 + 1e-12, 0.5),
             "v": arm(0.5, 0.5 + 1e-12)
         }}
    out = confidence.check(s)
    assert out["ranking"] == ["u", "v"]
    assert out["order_changes"] == []
    assert out["groups"] == [["u"], ["v"]]


def test_tied_at_base_arms_that_clearly_swap_are_reported_and_grouped():
    # u = (1, 0), v = (0, 1): both 50 at base, u first by name.
    # "a -5" (a=45, b=55): u = 45, v = 55, so v is clearly ahead -> a change.
    # "a +5" (a=55, b=45): u stays ahead -> no change.
    s = {"weights": {"dimensions": W, "parts": PW},
         "arms": {"u": arm(1.0, 0.0), "v": arm(0.0, 1.0)}}
    out = confidence.check(s)
    assert out["ranking"] == ["u", "v"]
    variants = [c["variant"] for c in out["order_changes"]]
    assert "a -5, judges median" in variants
    assert not any(v.startswith("a +5") for v in variants)
    assert next(c["order"] for c in out["order_changes"] if c["variant"] == "a -5, judges median") == ["v", "u"]
    assert out["groups"] == [["u", "v"]]


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
