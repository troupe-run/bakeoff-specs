import json
import pytest
from runner import paths
from runner.scoring import aggregate, inputs, values

LENSES = ("auditor", "maintainer", "newcomer")


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
    for arm in ("alpha", "control"):
        write_collected("p", arm, 1)
    return "p"


def _scores(pass_):
    return json.loads(aggregate.run(pass_).read_text())


def test_a_dimension_with_one_unmeasured_part_reweights_the_rest(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None,
                                            "mutation_state": "crashed"})
    write_judged(p, "test_names", "alpha", "01", [4, 4, 4])
    s = _scores(p)["arms"]["alpha"]["dimensions"]["code_quality"]
    assert s["unmeasured_parts"] == ["mutation"] and s["score"] == pytest.approx(15.0)


def test_owner_verdict_is_used_and_lenses_are_kept(p):
    write_collected(p, "alpha", 3)
    write_judged(p, "req_test_code", "alpha", "03", [1, 3, 4])
    v = paths.scoring_out(p) / "review" / "verdicts.jsonl"
    v.parent.mkdir(parents=True)
    v.write_text(json.dumps({"part": "req_test_code", "arm": "alpha", "step": 3, "score": 2, "reason": "r",
                             "decided": "owner"}) + "\n")
    st = _scores(p)["arms"]["alpha"]["dimensions"]["traceability"]["parts"]["req_test_code"]["steps"]["3"]
    assert st["score"] == 0.5 and st["lenses"] == {"auditor": 1, "maintainer": 3, "newcomer": 4} and st["disputed"]


def test_control_missing_for_a_step_leaves_time_unscored(p):
    write_collected(p, "alpha", 2)
    st = _scores(p)["arms"]["alpha"]["dimensions"]["time"]["parts"]["time"]["steps"]["2"]
    assert st["score"] is None and st["why"] == "no baseline for this step"


def test_unreviewed_all_fail_test_stops_aggregation(p, monkeypatch):
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {1: ["t-everyone-fails"]})
    monkeypatch.setattr(aggregate.inputs, "load_excluded",
                        lambda: inputs.Exclusions(frozenset(), frozenset(), []))
    with pytest.raises(inputs.InputError, match="t-everyone-fails"):
        aggregate.run(p)


def test_a_rerun_is_byte_identical(p):
    assert aggregate.run(p).read_bytes() == aggregate.run(p).read_bytes()


def _two_dimension_weights(monkeypatch):
    w = inputs.load_weights()
    monkeypatch.setattr(aggregate.inputs, "load_weights", lambda: inputs.Weights(
        {"correctness": 50.0, "code_quality": 50.0}, {"code_quality": {"mutation": 50.0}}, w.scales, w.report))


def test_total_is_renormalised_over_measured_dimension_weight_and_a_different_measured_set_is_flagged(
        tmp_state, monkeypatch):
    # R34 probe: x scores 45/50 on a (correctness), b (mutation) unmeasured; y scores 30/50 on both.
    # Renormalised: x = 100 * 45 / 50 = 90, y = 100 * 60 / 100 = 60. The plain sum would rank y (60) over x (45).
    (paths.RESULTS / "q").mkdir(parents=True)
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {})
    _two_dimension_weights(monkeypatch)
    write_collected("q", "x", 1, hidden={"passed": 9, "total": 10, "excluded": [], "per_test": {}},
                    quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None, "mutation_state": "crashed"})
    write_collected("q", "y", 1, hidden={"passed": 6, "total": 10, "excluded": [], "per_test": {}},
                    quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": 0.6, "mutation_state": "measured"})
    s = _scores("q")
    assert s["arms"]["x"]["total"] == pytest.approx(90.0) and s["arms"]["y"]["total"] == pytest.approx(60.0)
    assert s["arms"]["x"]["total_partial"] is True and s["arms"]["y"]["total_partial"] is False
    assert any(f.startswith("x: total renormalised") and "code_quality" in f for f in s["flags"])
    assert not any(f.startswith("y: total renormalised") for f in s["flags"])


def test_an_arm_with_no_measured_dimension_has_no_total_not_a_zero(tmp_state, monkeypatch):
    (paths.RESULTS / "q").mkdir(parents=True)
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {})
    _two_dimension_weights(monkeypatch)
    write_collected("q", "x", 1, hidden=values.missing("x", "gone"),
                    quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None, "mutation_state": "crashed"})
    write_collected("q", "y", 1)
    s = _scores("q")
    assert s["arms"]["x"]["total"] is None and s["arms"]["x"]["total_partial"] is True


def test_not_applicable_lenses_are_left_out_of_the_median_and_all_na_is_not_a_zero(p):
    write_collected(p, "alpha", 2)
    for lens, (st, sc) in zip(LENSES, [("ok", 4), ("not_applicable", None), ("ok", 2)]):
        f = paths.scoring_out(p) / "judged" / "hand_edit" / "alpha" / "02" / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": sc, "status": st, "evidence": [], "notes": ""}))
    for lens in LENSES:
        f = paths.scoring_out(p) / "judged" / "stale_updated" / "alpha" / "03" / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": None, "status": "not_applicable", "evidence": [], "notes": ""}))
    write_collected(p, "alpha", 3)
    parts = _scores(p)["arms"]["alpha"]["dimensions"]["coping"]["parts"]
    assert parts["hand_edit"]["steps"]["2"]["score"] == 0.75        # median of the two ok lenses (4, 2) = 3
    na = parts["stale_updated"]["steps"]["3"]
    assert na["score"] is None and na["why"] == "not applicable"


def test_draft_exclusions_are_flagged_and_owner_decided_ones_are_not(p, monkeypatch):
    entries = [{"id": "t-draft", "verdict": "defect", "reason": "r", "decided": "draft - awaiting owner"},
               {"id": "t-final", "verdict": "hard", "reason": "r", "decided": "owner 2026-10-05"}]
    monkeypatch.setattr(aggregate.inputs, "load_excluded",
                        lambda: inputs.Exclusions(frozenset({"t-draft"}), frozenset({"t-draft", "t-final"}), entries))
    flags = _scores(p)["flags"]
    assert any("t-draft" in f and "draft" in f for f in flags) and not any("t-final" in f for f in flags)


def _coping(pass_, arm="alpha"):
    return _scores(pass_)["arms"][arm]["dimensions"]["coping"]


def test_unequal_shares_reweight_by_points_over_measured_points(p):
    write_collected(p, "alpha", 2, regressions={"rate": 0.5, "baseline_step": 1},
                    churn={"lines": 0, "files": [], "total_lines": 0})
    write_collected(p, "control", 2)
    d = _coping(p)
    assert d["unmeasured_parts"] == ["hand_edit", "stale_updated"]
    # regressions 0.5 (7 pts), churn 0.5 (3 pts, equal lines = midpoint): 20 * (7*.5 + 3*.5) / 10
    assert d["score"] == pytest.approx(20 * (0.35 * 0.5 + 0.15 * 0.5) / 0.5)


def test_any_step_missing_violations_evidence_leaves_the_part_unscored(p):
    write_collected(p, "alpha", 2, violations=values.missing("x", "gone"))
    st = _scores(p)["arms"]["alpha"]["dimensions"]["setup"]["parts"]["violations"]["steps"]["arm"]
    assert st["score"] is None and st["why"] == "violations evidence missing for steps [2]"


def test_time_with_zero_passed_is_worst_and_baseline_zero_passed_is_unscored(p):
    zero = {"passed": 0, "total": 10, "excluded": [], "per_test": {}}
    write_collected(p, "alpha", 2, hidden=zero)
    write_collected(p, "control", 2)
    assert _scores(p)["arms"]["alpha"]["dimensions"]["time"]["parts"]["time"]["steps"]["2"]["score"] == 0.0
    write_collected(p, "alpha", 2)
    write_collected(p, "control", 2, hidden=zero)
    st = _scores(p)["arms"]["alpha"]["dimensions"]["time"]["parts"]["time"]["steps"]["2"]
    assert st["score"] is None and st["why"] == "baseline passed no tests"


def test_an_arm_with_a_different_step_set_is_flagged(p):
    write_collected(p, "control", 2)
    assert "alpha: steps collected [1] differ from the field [1, 2]" in _scores(p)["flags"]


def test_missing_baseline_records_are_flagged(p, tmp_state):
    import shutil
    shutil.rmtree(paths.scoring_out(p) / "collected" / "control")
    assert "baseline arm 'control' has no collected records" in _scores(p)["flags"]


def test_mutation_measured_without_a_score_says_so(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None,
                                            "mutation_state": "measured"})
    st = _scores(p)["arms"]["alpha"]["dimensions"]["code_quality"]["parts"]["mutation"]["steps"]["1"]
    assert st["why"] == "measured but no score"


@pytest.mark.parametrize("rows", [
    [{"part": "req_test_code", "arm": "alpha", "step": 3, "score": 5, "reason": "r", "decided": "owner"}],
    [{"part": "req_test_code", "arm": "alpha", "step": 3, "score": 2, "decided": "owner"}],
    [{"part": "req_test_code", "arm": "alpha", "step": 3, "score": 2, "reason": "r", "decided": "owner"}] * 2])
def test_bad_verdict_rows_raise_naming_the_row(p, rows):
    v = paths.scoring_out(p) / "review" / "verdicts.jsonl"
    v.parent.mkdir(parents=True)
    v.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(inputs.InputError, match="verdicts.jsonl line"):
        aggregate.run(p)


def test_a_weights_part_without_a_rubric_raises_input_error(p, monkeypatch):
    w = inputs.load_weights()
    parts = {**w.parts, "coping": {**w.parts["coping"], "mystery": 0.0}}
    monkeypatch.setattr(aggregate.inputs, "load_weights", lambda: inputs.Weights(w.dimensions, parts, w.scales))
    with pytest.raises(inputs.InputError, match="mystery"):
        aggregate.run(p)


def test_an_unmeasured_mutation_part_carries_the_evidence_why(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None,
                                            "mutation_state": "unmeasured",
                                            "mutation_why": "partial: under 50% of sampled mutants checked"})
    s = _scores(p)
    parts = json.dumps(s["arms"]["alpha"])
    assert "partial: under 50% of sampled mutants checked" in parts


def test_mixed_mutation_methods_across_arms_are_flagged_and_counted(p):
    q = {"mypy_errors": 0, "ruff_findings": 0, "mutation_score": 0.8, "mutation_state": "measured"}
    write_collected(p, "alpha", 1, quality={**q, "mutation_method": "mutmut"})
    write_collected(p, "control", 1, quality={**q, "mutation_method": "whole-suite-per-mutant"})
    s = _scores(p)
    assert s["mutation_methods"] == {"alpha": {"mutmut": 1}, "control": {"whole-suite-per-mutant": 1}}
    assert s["arms"]["alpha"]["dimensions"]["code_quality"]["parts"]["mutation"]["steps"]["1"]["method"] == "mutmut"
    assert any(f.startswith("mutation methods mixed") and "remeasure --all" in f for f in s["flags"])


def test_one_mutation_method_throughout_is_not_flagged(p):
    q = {"mypy_errors": 0, "ruff_findings": 0, "mutation_score": 0.8, "mutation_state": "measured",
         "mutation_method": "whole-suite-per-mutant"}
    write_collected(p, "alpha", 1, quality=q)
    write_collected(p, "control", 1, quality=q)
    s = _scores(p)
    assert not any(f.startswith("mutation methods mixed") for f in s["flags"])


def test_violations_are_deducted_by_severity_of_their_kind(p, monkeypatch):
    monkeypatch.setattr(aggregate.inputs, "load_violations",
                        lambda: inputs.ViolationSeverity(0.1, {"own-token-in-evidence": 0.5}))
    write_collected(p, "alpha", 1, violations=[{"kind": "own-token-in-evidence"}, {"kind": "setup-drift"}])
    write_collected(p, "alpha", 2, violations=[{"kind": "setup-drift"}])
    st = _scores(p)["arms"]["alpha"]["dimensions"]["setup"]["parts"]["violations"]["steps"]["arm"]
    assert st["score"] == pytest.approx(1 - 0.5 - 0.1 - 0.1)
    assert st["deducted"] == pytest.approx(0.7) and st["kinds"] == {"own-token-in-evidence": 1, "setup-drift": 2}
