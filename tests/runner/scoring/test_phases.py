import json
import shutil
from pathlib import Path

import pytest

from runner import config
from runner.scoring import inputs, phases, values

RULES = inputs.load_phase_rules()
FIX = Path(__file__).parent / "fixtures"
MINI = FIX / "mini"


def ev(t, name=None, kind="tool", **kw):
    return {"t": t, "kind": kind, "name": name, "input": kw.get("input", {}), "is_error": kw.get("is_error", False),
            "id": kw.get("id"), "output": kw.get("output", "")}


def test_reading_before_any_write_is_understanding():
    out = phases.classify([ev(0, "Read"), ev(10, "Write", input={"file_path": "src/a.py"}), ev(15, "Read")],
                          RULES, [])
    assert out["seconds"]["understand"] == 10 and out["seconds"]["implement"] == 5


def test_a_failed_test_run_turns_following_writes_into_rework_until_tests_pass():
    evs = [ev(0, "Write", input={"file_path": "src/a.py"}),
           ev(10, "Bash", input={"command": "uv run pytest -q"}, id="b1"),
           ev(20, kind="result", id="b1", is_error=True),
           ev(20, "Edit", input={"file_path": "src/a.py"}),
           ev(50, "Bash", input={"command": "uv run pytest -q"}, id="b2"),
           ev(60, kind="result", id="b2", output="3 passed"),
           ev(60, "Edit", input={"file_path": "src/b.py"}), ev(70, "Read")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["rework"] == 30 and s["implement"] == 20 and s["test"] == 20


def test_spec_writes_and_review_calls_have_their_own_phases():
    evs = [ev(0, "Write", input={"file_path": "specs/003/spec.md"}),
           ev(7, "Task", input={"description": "Review the plan"}), ev(10, "Read")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["specify"] == 7 and s["review"] == 3


def test_bad_transcript_lines_are_skipped_and_counted(tmp_path):
    d = tmp_path / "a1" / "-work-x"; d.mkdir(parents=True)
    (d / "s.jsonl").write_text('{"timestamp":"2026-10-05T00:00:00Z","type":"assistant","message":{"content":[]}}\n'
                               'not json\n{"truncated": ')
    evs, skipped = phases.events_from_transcripts(tmp_path)
    assert skipped == 2 and len(evs) == 1


def test_method_phases_label_turns_by_their_command():
    labels = [t["label"] for t in phases.method_phases(MINI / "alpha" / "01")["value"]]
    assert labels == ["/speckit-specify", "/speckit-plan"]       # fixture prompts


# --- beyond the brief's five: the parts of the rules the five do not reach ---------------------------------------

def test_method_phases_carry_each_turns_seconds_and_cost_and_label_free_text():
    assert phases.method_phases(MINI / "alpha" / "01")["value"] == [
        {"stem": "arm-a1-001", "label": "/speckit-specify", "seconds": 60.0, "usd": 1.0},
        {"stem": "arm-a1-002", "label": "/speckit-plan", "seconds": 40.0, "usd": 0.5}]
    assert [t["label"] for t in phases.method_phases(MINI / "control" / "02")["value"]] == ["(free text)"]


def _events_from_mini(tmp_path):
    d = tmp_path / "-work-repo"
    d.mkdir()
    shutil.copy(FIX / "transcript-mini.jsonl", d / "s.jsonl")
    return phases.events_from_transcripts(tmp_path)


def test_transcript_entries_become_tool_result_and_other_events_in_time_order(tmp_path):
    evs, skipped = _events_from_mini(tmp_path)
    assert skipped == 0
    assert [(e["t"] - evs[0]["t"], e["kind"], e["name"]) for e in evs] == [
        (0, "other", "(queue)"), (1, "other", "(prompt)"), (1, "other", None), (3, "tool", "Read"),
        (4, "result", None), (9, "tool", "Bash"), (19, "result", None), (25, "other", None)]
    assert evs[1]["input"] == {"label": "/speckit-plan"}            # the slash command inside <command-name>
    read_result, bash_result = evs[4], evs[6]
    assert read_result["id"] == "t1" and len(read_result["output"]) == 4000 and not read_result["is_error"]
    assert bash_result["id"] == "t2" and bash_result["is_error"] and bash_result["output"] == "1 failed, 2 passed"


def test_classifying_the_mini_transcript_counts_reading_then_a_failing_test(tmp_path):
    evs, _ = _events_from_mini(tmp_path)
    s = phases.classify(evs, RULES, [])["seconds"]
    # 0-1 queue op (before the prompt: a turn boundary, not counted); 1-9 understand; 9-25 test (the failing run's
    # result keeps the test phase until the closing text, the session's last event, which gets 0)
    assert s["understand"] == 8 and s["test"] == 16 and sum(s.values()) == 24


def test_the_gap_before_a_new_turn_prompt_is_not_arm_time():
    evs = [ev(0, "Read"), ev(10, kind="other"), ev(100, "(prompt)", kind="other", input={"label": "(free text)"}),
           ev(105, "Read"), ev(110, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["understand"] == 20 and sum(s.values()) == 20      # 0-10 and 100-110; 10-100 is between turns


def test_the_queue_operations_handing_in_a_prompt_also_end_the_previous_turn():
    evs = [ev(0, "Read"), ev(10, kind="other"), ev(90, "(queue)", kind="other"), ev(90, "(queue)", kind="other"),
           ev(100, "(prompt)", kind="other", input={"label": "(free text)"}), ev(105, "Read"), ev(110, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["understand"] == 20 and sum(s.values()) == 20


def test_entries_between_the_queue_operations_and_the_prompt_still_open_the_turn():
    # real transcripts: enqueue, dequeue, an attachment, then the prompt (pass1 speckitty/01 turn 6: a 35 min gap)
    evs = [ev(0, "Read"), ev(10, kind="other"), ev(90, "(queue)", kind="other"), ev(91, kind="other"),
           ev(100, "(prompt)", kind="other", input={"label": "(free text)"}), ev(105, "Read"), ev(110, kind="other")]
    assert sum(phases.classify(evs, RULES, [])["seconds"].values()) == 20


def test_a_turn_whose_command_is_a_review_marker_is_review_throughout():
    evs = [ev(0, "(prompt)", kind="other", input={"label": "/speckit-converge"}),
           ev(1, "Read"), ev(4, "Write", input={"file_path": "src/a.py"}), ev(10, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["review"] == 10 and s["implement"] == 0 and s["understand"] == 0


def test_a_new_turn_starts_in_understanding_again():
    evs = [ev(0, "Write", input={"file_path": "src/a.py"}), ev(5, "Read"), ev(10, kind="other"),
           ev(20, "(prompt)", kind="other", input={"label": "(free text)"}), ev(21, "Read"), ev(30, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["implement"] == 10 and s["understand"] == 10


def test_writes_under_the_arms_spec_paths_or_tests_or_absolute_work_paths_are_classified_by_path():
    sp = [config.SpecPath(path="design/", why="the method keeps its design here")]
    evs = [ev(0, "Write", input={"file_path": "/work/bakeoff-specs-x/design/a.txt"}),
           ev(2, "Edit", input={"file_path": "/work/bakeoff-specs-x/tests/test_a.py"}),
           ev(5, "Write", input={"file_path": "/work/bakeoff-specs-x/src/a.py"}), ev(9, kind="other")]
    s = phases.classify(evs, RULES, sp)["seconds"]
    assert s["specify"] == 2 and s["test"] == 3 and s["implement"] == 4


def test_a_passing_test_output_mentioning_no_failure_word_does_not_set_rework():
    evs = [ev(0, "Bash", input={"command": "uv run pytest"}, id="b"), ev(5, kind="result", id="b", output="9 passed"),
           ev(6, "Write", input={"file_path": "src/a.py"}), ev(8, kind="other")]
    assert phases.classify(evs, RULES, [])["seconds"]["implement"] == 2


def _step_with_transcript(tmp_path, entries, *, turns, po=10.0, owner=5.0):
    """turns: [(stem, prompt, duration_ms, cumulative usd)]."""
    from tests.runner.scoring.fixtures import make_mini
    d = tmp_path / "step"
    make_mini.w(d / "run.json", json.dumps({"po_seconds": po, "owner_wait_seconds": owner}))
    for stem, prompt, ms, cum in turns:
        make_mini.turn(d, stem, prompt, ms, cum)
    make_mini.w(d / "transcripts" / "a1" / "-work-repo" / "s.jsonl", "".join(json.dumps(e) + "\n" for e in entries))
    return d


def _at(sec):
    return f"2026-10-05T09:{sec // 60:02d}:{sec % 60:02d}.000Z"


def _prompt(sec, text):
    return {"type": "user", "timestamp": _at(sec), "message": {"content": text}}


def _tool(sec, name, inp):
    return {"type": "assistant", "timestamp": _at(sec),
            "message": {"content": [{"type": "tool_use", "id": f"u{sec}", "name": name, "input": inp}]}}


def test_common_phases_add_waiting_and_split_each_turns_cost_by_its_own_seconds(tmp_path):
    d = _step_with_transcript(tmp_path, [
        _prompt(0, "build it"), _tool(0, "Read", {"file_path": "a"}), _tool(10, "Write", {"file_path": "src/a.py"}),
        _tool(40, "Read", {"file_path": "a"}),
        _prompt(50, "/speckit-plan"), _tool(50, "Write", {"file_path": "specs/p.md"}), _tool(60, "Read", {})],
        turns=[("arm-a1-001", "build it", 40_000, 4.0), ("arm-a1-002", "/speckit-plan", 10_000, 5.0)])
    out = phases.common_phases(d, [], RULES)
    assert not values.is_missing(out)
    v = out["value"]
    assert v["seconds"] == {"understand": 10.0, "specify": 10.0, "implement": 30.0, "test": 0.0, "rework": 0.0,
                            "review": 0.0, "waiting": 15.0}
    # turn 1 ($4): 10 s understand, 30 s implement; turn 2 ($1): 10 s specify
    assert v["usd"] == {"understand": 1.0, "specify": 1.0, "implement": 3.0, "test": 0.0, "rework": 0.0,
                        "review": 0.0, "waiting": 0.0}
    assert v["skipped_lines"] == 0


def test_common_phases_without_transcripts_are_missing_not_zero(tmp_path):
    d = _step_with_transcript(tmp_path, [], turns=[("arm-a1-001", "x", 1000, 1.0)])
    shutil.rmtree(d / "transcripts")
    assert values.is_missing(phases.common_phases(d, [], RULES))


def test_when_transcript_turns_do_not_match_the_turn_records_cost_by_phase_is_unknown_not_guessed(tmp_path):
    d = _step_with_transcript(tmp_path, [_prompt(0, "build it"), _tool(0, "Read", {}), _tool(10, "Read", {})],
                              turns=[("arm-a1-001", "build it", 10_000, 1.0), ("arm-a1-002", "more", 10_000, 2.0)])
    v = phases.common_phases(d, [], RULES)["value"]
    assert v["usd"] is None and "1 turn prompts in the transcripts, 2 turn records" in v["usd_why"]
    assert v["seconds"]["understand"] == 10.0


def test_a_killed_last_turn_keeps_its_time_and_its_unknown_cost_is_named_not_split():
    v = phases.common_phases(MINI / "alpha" / "02", [], RULES)["value"]
    assert v["seconds"]["understand"] == 120.0 and v["seconds"]["waiting"] == 15.0   # 30 s + the killed turn's 90 s
    assert v["usd"]["understand"] == 0.5 and "arm-a2-002" in v["usd_why"]


def test_a_cost_absorbed_from_an_unknown_turn_is_split_over_both_turns_seconds():
    zero = {p: 0.0 for p in phases.PHASES}
    usd, unplaced = phases._split_usd([{"stem": "a", "usd": None}, {"stem": "b", "usd": 2.0}],
                                      [dict(zero, understand=10.0), dict(zero, implement=30.0)])
    assert usd["understand"] == 0.5 and usd["implement"] == 1.5 and unplaced == []


def _bash(t, cmd, id=None):
    return ev(t, "Bash", input={"command": cmd}, id=id)


def test_bash_write_targets_are_extracted_from_redirects_sed_tee_and_python():
    t = phases.bash_write_targets
    assert t("cd /work/r; cat > src/a.py <<'EOF'\nx = 1\nEOF", RULES) == ["src/a.py"]
    assert t("cat >> tests/test_a.py <<EOF\nEOF", RULES) == ["tests/test_a.py"]
    assert t("sed -i 's/x/y/' tests/test_a.py", RULES) == ["tests/test_a.py"]
    assert t("echo hi | tee -a docs/notes.md", RULES) == ["docs/notes.md"]
    assert t("python3 - <<'EOF'\nopen('specs/x.md', 'w').write(s)\nEOF", RULES) == ["specs/x.md"]
    assert t("python3 - <<'EOF'\nPath(\"src/b.py\").write_text(s)\nEOF", RULES) == ["src/b.py"]
    assert t("python3 - <<'EOF'\np = 'tests/test_a.py'; s = open(p).read()\nopen(p, 'w').write(s)\nEOF",
             RULES) == ["tests/test_a.py"]                                 # the variable's last string assignment
    assert t("sed -i 's/a -> b/c/' src/a.py; echo \"x >, y\"", RULES) == ["src/a.py"]   # no target from '>,'
    assert t("cd /work/r; uv run pytest -q 2>&1 | tail", RULES) is None       # 2>&1 is not a file write
    assert t("ls > /dev/null", RULES) is None and t("uv run pytest | tee /tmp/log", RULES) is None   # outside the repo
    assert t("python3 - <<'EOF'\nif a > b:\n    pass\nEOF", RULES) is None        # a comparison in a heredoc body
    assert t("grep -n foo src/a.py", RULES) is None                           # not a write at all


def test_a_bash_write_is_classified_by_its_target_path():
    evs = [_bash(0, "cat > src/a.py <<EOF\nEOF"), _bash(4, "sed -i 's/x/y/' tests/test_a.py"),
           _bash(6, "python3 - <<'EOF'\nopen('/work/bakeoff-specs-x/specs/x.md', 'w').write(s)\nEOF"),
           ev(9, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["implement"] == 4 and s["test"] == 2 and s["specify"] == 3 and s["understand"] == 0


def test_a_bash_write_without_a_readable_target_is_implementation_or_rework():
    unreadable = "python3 - <<'EOF'\nopen(sys.argv[1], 'w').write(s)\nEOF"
    assert phases.bash_write_targets(unreadable, RULES) == []
    evs = [ev(0, "Read"), _bash(2, unreadable), _bash(5, "uv run pytest", id="b"),
           ev(6, kind="result", id="b", output="1 failed, 2 passed"), _bash(6, unreadable), ev(10, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["understand"] == 2 and s["implement"] == 3 and s["test"] == 1 and s["rework"] == 4


def test_a_passing_run_that_prints_error_inside_its_output_does_not_set_rework():
    evs = [_bash(0, "uv run troupe config get x", id="b"),
           ev(1, kind="result", id="b", output="Error: unknown actor 'bogus'\nexit=2"),
           ev(1, "Write", input={"file_path": "src/a.py"}), ev(3, kind="other")]
    assert phases.classify(evs, RULES, [])["seconds"]["implement"] == 2


@pytest.mark.parametrize("output", ["1 failed, 3 passed in 0.2s", "2 errors in 0.1s", "Found 3 errors in 1 file",
                                    "FAILED tests/test_a.py::test_x - assert 1 == 2"])
def test_a_test_summary_reporting_failures_sets_rework(output):
    evs = [_bash(0, "uv run pytest", id="b"), ev(1, kind="result", id="b", output=output),
           ev(1, "Write", input={"file_path": "src/a.py"}), ev(3, kind="other")]
    assert phases.classify(evs, RULES, [])["seconds"]["rework"] == 2


SAMPLE = FIX / "phase-sample.json"


@pytest.mark.skip(reason="awaiting owner check of the phase sample")
def test_the_classifier_still_reproduces_the_owner_checked_sample():
    sample = json.loads(SAMPLE.read_text())
    assert not sample["checked_by"].startswith("pending")
    for arm, want in sample["runs"].items():
        step_dir = Path(__file__).parents[3] / "results" / "pass1" / arm / "04"
        got = phases.common_phases(step_dir, config.load_arm(arm).spec_paths, RULES)["value"]
        assert got == want, arm
