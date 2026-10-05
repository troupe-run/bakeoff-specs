from pathlib import Path
from runner import paths
from runner.scoring import evidence, values

MINI = Path(__file__).parent / "fixtures" / "mini"


def test_arm_time_uses_only_the_final_attempt():
    # control/02 has attempt 1 (7 s) and attempt 2 (20 s): only attempt 2 counts.
    t = evidence.arm_time(MINI / "control" / "02")["value"]
    assert t["attempt"] == 2 and [x["stem"] for x in t["turns"]] == ["arm-a2-001"] and t["seconds"] == 20.0


def test_a_killed_final_turn_makes_the_step_time_missing_until_task_8():
    # alpha/02's final attempt ends in arm-a2-002 with no result line; _killed_seconds is a stub (Task 8).
    m = evidence.arm_time(MINI / "alpha" / "02")
    assert values.is_missing(m) and "arm-a2-002" in m["missing"] and "a1" not in m["missing"].split("/")[-1]


def test_turn_cost_is_the_difference_of_cumulative_totals():
    turns = evidence.arm_time(MINI / "alpha" / "01")["value"]["turns"]
    assert [round(x["usd"], 2) for x in turns] == [1.0, 0.5]      # fixture: cumulative 1.0 then 1.5


def test_mutation_state_distinguishes_crashed_from_measured():
    q = evidence.quality(MINI / "alpha" / "01")["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.8
    assert evidence.quality(MINI / "control" / "01")["value"]["mutation_state"] == "crashed"


def test_questions_come_from_both_runs_labelled():
    qs = evidence.questions(MINI / "alpha" / "01")["value"]
    assert {q["run"] for q in qs} == {"a", "b"}


def test_a_missing_file_is_missing_with_its_path():
    m = evidence.hidden_summary(MINI / "control" / "02")
    assert values.is_missing(m) and m["missing"].endswith("control/02/hidden/summary.json")


def test_costs_and_violations_read_the_fixture():
    assert evidence.costs(MINI / "alpha" / "01")["value"] == {"scored_usd": 1.5, "po_usd": 0.25, "discovery_usd": 0.75}
    assert evidence.violations(MINI / "alpha" / "02")["value"] == [{"rule": "no-network", "detail": "curl"}]
    assert evidence.run_record(MINI / "alpha" / "02")["value"]["attempts"] == 2


def test_the_fixture_is_rebuildable_from_its_generator(tmp_path, monkeypatch):
    from tests.runner.scoring.fixtures import make_mini
    monkeypatch.setattr(make_mini, "ROOT", tmp_path / "mini")
    make_mini.build()
    for f in sorted(p for p in MINI.rglob("*") if p.is_file()):
        assert (tmp_path / "mini" / f.relative_to(MINI)).read_bytes() == f.read_bytes(), f
