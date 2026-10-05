import json
import dataclasses
import shutil
from pathlib import Path
import pytest
from runner import paths
from runner.scoring import collect

MINI = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture
def mini_pass(tmp_state):
    shutil.copytree(MINI, paths.RESULTS / "mini")
    return "mini"


def test_arms_are_step_holding_directories(mini_pass):
    assert collect.arms(paths.RESULTS / mini_pass) == ["alpha", "control"]


def test_collect_writes_one_record_per_arm_step(mini_pass):
    out = collect.run(mini_pass, docker=False)
    assert sorted(p.relative_to(paths.scoring_out(mini_pass)).as_posix() for p in out) == [
        "collected/alpha/01.json", "collected/alpha/02.json", "collected/control/01.json",
        "collected/control/02.json"]


def test_collect_is_byte_identical_on_a_rerun(mini_pass):
    a = [p.read_bytes() for p in collect.run(mini_pass, docker=False)]
    b = [p.read_bytes() for p in collect.run(mini_pass, docker=False)]
    assert a and a == b


def test_a_step_without_hidden_results_is_missing_not_zero(mini_pass):
    collect.run(mini_pass, docker=False)
    rec = json.loads((paths.scoring_out(mini_pass) / "collected" / "control" / "02.json").read_text())
    assert "missing" in rec["hidden"] and "value" not in rec["hidden"]
    assert "missing" in rec["regressions"]


def test_without_docker_churn_is_deferred(mini_pass):
    collect.run(mini_pass, docker=False)
    rec = json.loads((paths.scoring_out(mini_pass) / "collected" / "alpha" / "02.json").read_text())
    assert rec["churn"]["why"].startswith("deferred")


def _hidden_summary(arm_dir: Path, n: int, tests: dict) -> None:
    f = arm_dir / f"{n:02d}" / "hidden" / "summary.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"scoreable": True, "tests": tests}))


def _rec(pass_: str, arm: str, n: int) -> dict:
    return json.loads((paths.scoring_out(pass_) / "collected" / arm / f"{n:02d}.json").read_text())


@pytest.fixture
def gap_pass(tmp_state):
    arm = paths.RESULTS / "gap" / "solo"
    _hidden_summary(arm, 1, {"t::a": "passed", "t::b": "passed"})
    (arm / "02").mkdir()                                  # step 2: no hidden summary
    _hidden_summary(arm, 3, {"t::a": "passed", "t::b": "failed"})
    return "gap"


def test_regressions_name_the_baseline_step_when_a_step_has_no_hidden_results(gap_pass):
    collect.run(gap_pass, docker=False)
    r = _rec(gap_pass, "solo", 3)["regressions"]["value"]
    assert r["baseline_step"] == 1 and r["regressed"] == ["t::b"]


def test_step_one_regressions_are_missing_with_nothing_to_compare_against(gap_pass):
    collect.run(gap_pass, docker=False)
    r = _rec(gap_pass, "solo", 1)["regressions"]
    assert "missing" in r and r["why"] == "step 1: nothing to compare against"


def test_regressions_are_missing_when_no_earlier_step_is_scoreable(tmp_state):
    arm = paths.RESULTS / "late" / "solo"
    (arm / "01").mkdir(parents=True)
    _hidden_summary(arm, 2, {"t::a": "passed"})
    collect.run("late", docker=False)
    r = _rec("late", "solo", 2)["regressions"]
    assert "missing" in r and "value" not in r and "no earlier" in r["why"]


def test_hidden_counts_drop_defect_tests_and_list_them_as_excluded(tmp_state, monkeypatch):
    arm = paths.RESULTS / "excl" / "solo"
    _hidden_summary(arm, 1, {"t::a": "passed", "t::bad": "failed", "t::c": "failed"})
    real = collect.inputs.load_excluded()
    monkeypatch.setattr(collect.inputs, "load_excluded",
                        lambda: dataclasses.replace(real, defects=frozenset({"t::bad"})))
    collect.run("excl", docker=False)
    h = _rec("excl", "solo", 1)["hidden"]["value"]
    assert (h["passed"], h["total"], h["excluded"]) == (1, 2, ["t::bad"])
    assert "t::bad" not in h["per_test"]


def test_a_rerun_clears_stale_collected_records(mini_pass):
    collect.run(mini_pass, docker=False)
    stale = paths.scoring_out(mini_pass) / "collected" / "gone" / "01.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    collect.run(mini_pass, docker=False)
    assert not stale.exists()


def test_collect_records_the_reported_not_scored_evidence(mini_pass):
    # R36: owner review time, tracker, N.a stop and re-runs/harness faults are collected (each a value or missing)
    collect.run(mini_pass, docker=False)
    rec = json.loads((paths.scoring_out(mini_pass) / "collected" / "alpha" / "01.json").read_text())
    assert {"owner_review", "tracker", "discovery", "runs"} <= set(rec)
    assert rec["owner_review"]["value"]["seconds"] >= 0 and rec["runs"]["value"]["attempts"] is not None
    assert "missing" in rec["tracker"] and "missing" in rec["discovery"]     # the mini fixture has neither file
