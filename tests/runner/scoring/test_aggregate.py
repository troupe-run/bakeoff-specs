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
           "cost": values.val({}, "x"), "violations": values.val([], "x"),
           "questions": values.val({"items": [], "skipped_lines": 0, "discovery": "absent"}, "x"),   # evidence's shape
           "churn": values.val({"lines": 0, "files": [], "total_lines": 0}, "x"),
           "phases": {"method": values.val([], "x"), "common": values.val({}, "x")}}
    for k, v in fields.items():
        rec[k] = v if isinstance(v, dict) and ("value" in v or "missing" in v) else values.val(v, "x")
    f = paths.scoring_out(pass_) / "collected" / arm / f"{step:02d}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(values.dump(rec))


def lens_names(part):
    return [l["name"] for l in inputs.load_rubrics()[part].lenses]


def write_judged(pass_, part, arm, key, scores):
    for lens, s in zip(lens_names(part), scores):
        f = paths.scoring_out(pass_) / "judged" / part / arm / key / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": s, "status": "ok", "evidence": ["x"], "notes": ""}))


def write_arm_violations(pass_, arm, value):
    """The collected arm-level leaf (R38): `value` is a list of violations, or a values.missing(...)."""
    rec = value if isinstance(value, dict) else values.val(value, "x")
    f = paths.scoring_out(pass_) / "collected-arm" / f"{arm}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(values.dump({"arm": arm, "arm_violations": rec}))


@pytest.fixture
def p(tmp_state, monkeypatch):
    (paths.RESULTS / "p").mkdir(parents=True)
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {})
    for arm in ("alpha", "control"):
        write_collected("p", arm, 1)
        write_arm_violations("p", arm, [])
    return "p"


def _scores(pass_):
    return json.loads(aggregate.run(pass_).read_text())


def test_a_dimension_with_one_unmeasured_part_reweights_the_rest(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None,
                                            "mutation_state": "crashed"})
    _quality_files(p, "alpha", 1, size={"type_lines": 1000, "lint_lines": 1000}, ruff=[])
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
    for lens, (st, sc) in zip(lens_names("hand_edit"), [("ok", 4), ("not_applicable", None), ("ok", 2)]):
        f = paths.scoring_out(p) / "judged" / "hand_edit" / "alpha" / "02" / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": sc, "status": st, "evidence": [], "notes": ""}))
    for lens in lens_names("stale_updated"):
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


def test_a_judged_step_with_fewer_than_three_ok_lenses_is_marked_thin(p):
    write_collected(p, "alpha", 3)
    write_judged(p, "req_test_code", "alpha", "03", [2, 3])                 # the third lens never answered
    write_judged(p, "change_reason", "alpha", "03", [2, 3, 3])
    parts = _scores(p)["arms"]["alpha"]["dimensions"]["traceability"]["parts"]
    assert parts["req_test_code"]["steps"]["3"]["thin"] is True
    assert parts["change_reason"]["steps"]["3"]["thin"] is False


def test_a_lens_file_not_named_in_the_rubric_is_ignored_and_flagged(p):
    write_collected(p, "alpha", 3)
    write_judged(p, "req_test_code", "alpha", "03", [3, 3, 3])
    f = paths.scoring_out(p) / "judged" / "req_test_code" / "alpha" / "03" / "intruder.json"
    f.write_text(json.dumps({"score": 0, "status": "ok", "evidence": ["x"], "notes": ""}))
    s = _scores(p)
    st = s["arms"]["alpha"]["dimensions"]["traceability"]["parts"]["req_test_code"]["steps"]["3"]
    assert st["score"] == 0.75 and "intruder" not in st["lenses"] and st["disputed"] is False
    assert "alpha: req_test_code 03: lens file(s) ['intruder'] are not lenses of the rubric; ignored" in s["flags"]


def _viol(p):
    return _scores(p)["arms"]["alpha"]["dimensions"]["setup"]["parts"]["violations"]["steps"]["arm"]


def test_arm_level_violations_are_priced_with_the_step_ones(p, monkeypatch):
    monkeypatch.setattr(aggregate.inputs, "load_violations",
                        lambda: inputs.ViolationSeverity(0.1, {"own-token-in-evidence": 0.5, "link-in-home": 0.2}))
    write_collected(p, "alpha", 1, violations=[{"kind": "setup-drift"}])
    write_arm_violations(p, "alpha", [{"step": 1, "run": "b", "kind": "own-token-in-evidence"},
                                      {"kind": "link-in-home", "path": "/h/.config"}])
    st = _viol(p)
    assert st["score"] == pytest.approx(1 - 0.1 - 0.5 - 0.2)
    assert st["kinds"] == {"setup-drift": 1, "own-token-in-evidence": 1, "link-in-home": 1}
    assert st["arm_level"] == 2


def test_an_unreadable_arm_violations_file_leaves_the_part_unscored_not_clean(p):
    write_arm_violations(p, "alpha", values.missing("results/p/alpha/arm-violations.jsonl", "unreadable: bad line"))
    st = _viol(p)
    assert st["score"] is None and "arm-level violations" in st["why"] and "unreadable" in st["why"]


def test_arm_violations_never_collected_leaves_the_part_unscored(p):
    (paths.scoring_out(p) / "collected-arm" / "alpha.json").unlink()
    st = _viol(p)
    assert st["score"] is None and "arm-level violations" in st["why"]


def test_the_highest_priced_arm_level_violation_is_not_uncounted(p):
    write_arm_violations(p, "alpha", [{"step": 1, "run": "b", "kind": "own-token-in-evidence"}])
    assert _viol(p)["score"] == pytest.approx(1 - inputs.load_violations().of("own-token-in-evidence"))


def test_orchestrates_before_run_drift_and_stepflows_after_attempt_drift_are_distinct_events(p, monkeypatch):
    """Pinned (R38 fix round 1, item 3): stepflow's post-attempt check (step-level run.json arm_violations: run and
    attempt, no step) and orchestrate's pre-run verify (arm-level file, `before_run`) look at different moments, so the
    same check id in the same step and run is two detections, both priced. Own-token scans cannot double up either:
    stepflow redacts in place first, so orchestrate's later scan finds nothing left."""
    monkeypatch.setattr(aggregate.inputs, "load_violations", lambda: inputs.ViolationSeverity(0.25, {}))
    write_collected(p, "alpha", 1, violations=[{"run": "b", "attempt": 1, "kind": "setup-drift", "check": "common.origin"}])
    write_arm_violations(p, "alpha", [{"step": 1, "run": "b", "kind": "setup-drift", "check": "common.origin",
                                       "before_run": True}])
    assert _viol(p)["score"] == pytest.approx(0.5)


# --- types and lint: per-KLOC, safe fixes weighted (owner, 2026-10-10) ----------------------------------------------

def _quality_files(pass_, arm, step, *, size=None, ruff=None):
    q = paths.RESULTS / pass_ / arm / f"{step:02d}" / "quality"
    q.mkdir(parents=True, exist_ok=True)
    if size is not None:
        (q / "size.json").write_text(json.dumps(size))
    if ruff is not None:
        (q / "ruff.json").write_text(json.dumps(ruff))


def _cq(pass_, arm="alpha", step="1"):
    parts = _scores(pass_)["arms"][arm]["dimensions"]["code_quality"]["parts"]
    return parts["types"]["steps"][step], parts["lint"]["steps"][step]


SAFE, UNSAFE = {"code": "I001", "fix": {"applicability": "safe"}}, {"code": "B006", "fix": {"applicability": "unsafe"}}


def test_types_and_lint_are_per_kloc_with_safe_fixes_weighted(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 4, "ruff_findings": 12, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 2000, "lint_lines": 4000},
                   ruff=[SAFE] * 10 + [UNSAFE, {"code": "E501", "fix": None}])
    t, l = _cq(p)
    assert t["score"] == pytest.approx(1 - (4 * 1000 / 2000) / 10) and t["lines"] == 2000 and t["errors"] == 4
    assert l["weighted"] == pytest.approx(3.0) and l["safe_fixes"] == 10 and l["findings"] == 12
    assert l["score"] == pytest.approx(1 - (3.0 * 1000 / 4000) / 10)


def test_types_and_lint_floor_at_zero(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 50, "ruff_findings": 30, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 1000, "lint_lines": 1000}, ruff=[UNSAFE] * 30)
    t, l = _cq(p)
    assert t["score"] == 0.0 and l["score"] == 0.0


def test_twenty_unsorted_imports_cost_a_tenth_of_twenty_type_errors(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 20, "ruff_findings": 20, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 10000, "lint_lines": 10000}, ruff=[SAFE] * 20)
    t, l = _cq(p)
    assert t["score"] == pytest.approx(0.8) and l["score"] == pytest.approx(0.98)


def test_no_size_measured_leaves_both_parts_unmeasured_not_zero(p):
    write_collected(p, "alpha", 1)
    _quality_files(p, "alpha", 1, ruff=[])
    t, l = _cq(p)
    assert t == {"score": None, "why": "no size measured"} and l == {"score": None, "why": "no size measured"}
    cq = _scores(p)["arms"]["alpha"]["dimensions"]["code_quality"]
    assert {"types", "lint"} <= set(cq["unmeasured_parts"])


def test_a_failed_size_measurement_is_unmeasured_with_its_reason(p):
    write_collected(p, "alpha", 1)
    _quality_files(p, "alpha", 1, size={"lint_lines": None, "type_lines": None, "error": "timed out"}, ruff=[])
    t, l = _cq(p)
    assert t["score"] is None and "timed out" in t["why"] and l["score"] is None


def test_crashed_mypy_or_ruff_is_unmeasured_for_its_own_part_only(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": None, "ruff_findings": 0, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 100, "lint_lines": 100}, ruff=[])
    t, l = _cq(p)
    assert t == {"score": None, "why": "mypy crashed or timed out"} and l["score"] == 1.0
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": None, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    t, l = _cq(p)
    assert t["score"] == 1.0 and l == {"score": None, "why": "ruff crashed or timed out"}


def test_lint_reads_the_harness_ruleset_never_the_arms_own_config(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 2, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 1000, "lint_lines": 1000}, ruff=[UNSAFE, UNSAFE])
    (paths.RESULTS / p / "alpha" / "01" / "quality" / "ruff-arm.json").write_text("[]")    # the arm switched it off
    assert _cq(p)[1]["score"] == pytest.approx(0.8)


def test_lint_unreadable_or_disagreeing_findings_are_unmeasured(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 3, "mutation_score": 0.8,
                                            "mutation_state": "measured"})
    _quality_files(p, "alpha", 1, size={"type_lines": 1000, "lint_lines": 1000}, ruff=[UNSAFE])
    assert _cq(p)[1]["score"] is None and "summary 3" in _cq(p)[1]["why"]
    (paths.RESULTS / p / "alpha" / "01" / "quality" / "ruff.json").unlink()
    assert _cq(p)[1]["score"] is None and "unreadable" in _cq(p)[1]["why"]


def test_zero_lines_is_unmeasured_not_a_division(p):
    write_collected(p, "alpha", 1)
    _quality_files(p, "alpha", 1, size={"type_lines": 0, "lint_lines": 0}, ruff=[])
    t, l = _cq(p)
    assert t["score"] is None and l["score"] is None


# ---- interaction n/a decided by the question log, not by judge vote (owner rule, 2026-10-10) ----------------------

def _qlog(*kinds, run="b"):
    return {"items": [{"run": run, "n": i, "kind": k, "answered_by": "po", "escalated": [], "fallback": []}
                      for i, k in enumerate(kinds, 1)], "skipped_lines": 0, "discovery": "absent"}


def _write_lenses(pass_, part, arm, key, answers):
    for lens, (st, sc) in zip(lens_names(part), answers):
        f = paths.scoring_out(pass_) / "judged" / part / arm / key / f"{lens}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"score": sc, "status": st, "evidence": [], "notes": ""}))


def _interaction_step(pass_, part, step, arm="alpha"):
    return _scores(pass_)["arms"][arm]["dimensions"]["interaction"]["parts"][part]["steps"][str(step)]


@pytest.mark.parametrize("part", ["question_value", "research_first"])
def test_no_question_in_the_log_makes_the_step_na_even_when_lenses_scored(p, part):
    write_collected(p, "alpha", 2, questions=_qlog("next_command", "step_done", "approval"))
    _write_lenses(p, part, "alpha", "02", [("ok", 0), ("not_applicable", None), ("ok", 3)])
    st = _interaction_step(p, part, 2)
    assert st["score"] is None and st["why"] == "not applicable (no question asked)"
    assert st["asked"] is False and st["disputed"] is False and st["lenses"] == {}


@pytest.mark.parametrize("run", ["a", "b"])
def test_a_question_in_either_run_ignores_na_lenses_and_takes_the_median_of_the_scorers(p, run):
    write_collected(p, "alpha", 2, questions=_qlog("step_done", "question", run=run))
    _write_lenses(p, "question_value", "alpha", "02", [("not_applicable", None), ("not_applicable", None), ("ok", 2)])
    st = _interaction_step(p, "question_value", 2)
    assert st["asked"] is True and st["score"] == 0.5 and st["lenses"] == {lens_names("question_value")[2]: 2}


def test_a_question_asked_but_every_lens_na_is_unmeasured_and_says_so(p):
    write_collected(p, "alpha", 2, questions=_qlog("question"))
    _write_lenses(p, "research_first", "alpha", "02", [("not_applicable", None)] * 3)
    st = _interaction_step(p, "research_first", 2)
    assert st["score"] is None and "every lens answered not_applicable" in st["why"]


def test_no_question_and_no_lens_files_is_na_not_unjudged(p):
    write_collected(p, "alpha", 2, questions=_qlog("step_done"))
    assert _interaction_step(p, "question_value", 2)["why"] == "not applicable (no question asked)"


def _owner(pass_, part, step, score):
    v = paths.scoring_out(pass_) / "review" / "verdicts.jsonl"
    v.parent.mkdir(parents=True, exist_ok=True)
    v.write_text(json.dumps({"part": part, "arm": "alpha", "step": step, "score": score, "reason": "r",
                             "decided": "owner"}) + "\n")


def test_an_owner_score_overrides_a_no_question_record(p):
    write_collected(p, "alpha", 2, questions=_qlog("step_done"))
    _write_lenses(p, "question_value", "alpha", "02", [("not_applicable", None)] * 3)
    _owner(p, "question_value", 2, 3)
    st = _interaction_step(p, "question_value", 2)
    assert st["score"] == 0.75 and st["owner"]["score"] == 3


def test_an_owner_na_overrides_a_question_asked_record(p):
    write_collected(p, "alpha", 2, questions=_qlog("question"))
    _write_lenses(p, "question_value", "alpha", "02", [("ok", 1), ("ok", 2), ("ok", 3)])
    _owner(p, "question_value", 2, None)
    st = _interaction_step(p, "question_value", 2)
    assert st["score"] is None and st["why"] == "not applicable" and "owner" in st


def test_a_missing_question_log_falls_back_to_the_lenses_and_is_flagged(p):
    write_collected(p, "alpha", 2, questions=values.missing("x", "gone"))
    _write_lenses(p, "question_value", "alpha", "02", [("ok", 0), ("not_applicable", None), ("ok", 2)])
    s = _scores(p)
    st = s["arms"]["alpha"]["dimensions"]["interaction"]["parts"]["question_value"]["steps"]["2"]
    assert st["asked"] is None and st["score"] == 0.25
    assert "alpha: question_value 02: question log missing; n/a decided by the lenses, not the record" in s["flags"]


def test_parts_without_not_applicable_ignore_the_question_log(p):
    write_collected(p, "alpha", 2, questions=_qlog("step_done"))
    write_judged(p, "gates", "alpha", "02", [4, 4, 4])
    st = _interaction_step(p, "gates", 2)
    assert st["score"] == 1.0 and "asked" not in st
