import gzip
import json
import shutil
from pathlib import Path
from runner import paths
from runner.scoring import evidence, values

MINI = Path(__file__).parent / "fixtures" / "mini"


def test_arm_time_uses_only_the_final_attempt():
    # control/02 has attempt 1 (7 s) and attempt 2 (20 s): only attempt 2 counts.
    t = evidence.arm_time(MINI / "control" / "02")["value"]
    assert t["attempt"] == 2 and [x["stem"] for x in t["turns"]] == ["arm-a2-001"] and t["seconds"] == 20.0
    assert round(t["turns"][0]["usd"], 2) == 0.9      # cumulative resets at the attempt boundary: 0.9, not 0.9 - 0.4


def test_a_killed_final_turn_counts_the_span_of_its_transcript_entries_and_is_flagged():
    # alpha/02's final attempt ends in arm-a2-002 with no result line; its transcript entries run 10:00:00-10:01:30.
    t = evidence.arm_time(MINI / "alpha" / "02")["value"]
    killed = t["turns"][-1]
    assert killed == {"stem": "arm-a2-002", "seconds": 90.0, "usd": None, "killed": True}
    assert t["seconds"] == 30.0 + 90.0


def test_a_killed_turn_without_transcript_entries_makes_the_step_time_missing(tmp_path):
    d = tmp_path / "02"
    shutil.copytree(MINI / "alpha" / "02", d)
    shutil.rmtree(d / "transcripts")
    m = evidence.arm_time(d)
    assert values.is_missing(m) and "arm-a2-002" in m["why"]


def test_turn_cost_is_the_difference_of_cumulative_totals():
    turns = evidence.arm_time(MINI / "alpha" / "01")["value"]["turns"]
    assert [round(x["usd"], 2) for x in turns] == [1.0, 0.5]      # fixture: cumulative 1.0 then 1.5


def test_mutation_state_distinguishes_crashed_from_measured():
    q = evidence.quality(MINI / "alpha" / "01")["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.8
    assert evidence.quality(MINI / "control" / "01")["value"]["mutation_state"] == "crashed"


def test_questions_come_from_both_runs_labelled():
    qs = evidence.questions(MINI / "alpha" / "01")["value"]
    assert {q["run"] for q in qs["items"]} == {"a", "b"} and qs["skipped_lines"] == 0 and qs["discovery"] == "present"


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
    files = lambda r: {p.relative_to(r) for p in r.rglob("*") if p.is_file()}
    assert files(tmp_path / "mini") == files(MINI)
    for f in sorted(p for p in MINI.rglob("*") if p.is_file()):
        assert (tmp_path / "mini" / f.relative_to(MINI)).read_bytes() == f.read_bytes(), f


def _step(tmp_path, *result_lines_per_turn):
    for i, lines in enumerate(result_lines_per_turn, 1):
        p = tmp_path / "turns" / f"arm-a1-{i:03d}.stream.jsonl.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(p, "wt") as f:
            for l in lines:
                f.write(json.dumps(l) + "\n")
    return tmp_path


def _res(**kw):
    return [{"type": "result", "subtype": "success", "is_error": False, **kw}]


def test_a_result_without_duration_makes_the_step_time_missing_naming_the_turn(tmp_path):
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0), _res(total_cost_usd=2.0))
    m = evidence.arm_time(d)
    assert values.is_missing(m) and "arm-a1-002" in m["why"]


def test_a_result_without_cost_leaves_usd_unknown_and_the_next_turn_absorbs_it(tmp_path):
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0), _res(duration_ms=2000),
              _res(duration_ms=3000, total_cost_usd=2.5))
    t = evidence.arm_time(d)["value"]["turns"]
    assert [x["usd"] for x in t] == [1.0, None, 1.5]
    assert [x.get("absorbs_previous", False) for x in t] == [False, False, True]


def test_an_error_turn_still_counts_as_real_time(tmp_path):
    d = _step(tmp_path, _res(duration_ms=4000, total_cost_usd=1.0, is_error=True))
    assert evidence.arm_time(d)["value"]["seconds"] == 4.0


def test_an_absent_scored_questions_file_is_missing(tmp_path):
    m = evidence.questions(tmp_path)
    assert values.is_missing(m) and m["missing"].endswith("questions.jsonl")


def test_a_malformed_question_line_is_skipped_and_counted_and_the_rest_kept(tmp_path):
    (tmp_path / "questions.jsonl").write_text('{"n": 1, "kind": "x"}\nnot json\n{"n": 2, "kind": "y"}\n')
    v = evidence.questions(tmp_path)["value"]
    assert [q["n"] for q in v["items"]] == [1, 2] and v["skipped_lines"] == 1


def test_an_absent_discovery_questions_file_is_reported_absent_not_an_error(tmp_path):
    (tmp_path / "questions.jsonl").write_text('{"n": 1}\n')
    v = evidence.questions(tmp_path)["value"]
    assert v["discovery"] == "absent" and [q["run"] for q in v["items"]] == ["b"]
