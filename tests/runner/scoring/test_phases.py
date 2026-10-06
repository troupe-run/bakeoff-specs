import json
import shutil
from pathlib import Path

import pytest

from runner import config, paths
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


@pytest.mark.skipif(not (paths.RESULTS / "pass1").is_dir(), reason="results/pass1 snapshot absent")
def test_the_classifier_still_reproduces_the_owner_checked_sample():
    sample = json.loads(SAMPLE.read_text())
    assert not sample["checked_by"].startswith("pending")
    for arm, want in sample["runs"].items():
        step_dir = paths.RESULTS / "pass1" / arm / "04"
        got = phases.common_phases(step_dir, config.load_arm(arm).spec_paths, RULES)["value"]
        assert got == want, arm


# --- fix round 4: damaged transcripts, malformed entries, shell sanitising ------------------------------------------

def _entries(n):
    """n distinct timestamped assistant entries (distinct text, so gzip cannot squeeze them into one block)."""
    import hashlib
    return "".join(json.dumps({"type": "assistant", "timestamp": _at(i), "message": {"content": [
        {"type": "text", "text": hashlib.sha256(str(i).encode()).hexdigest() * 8}]}}) + "\n" for i in range(n))


def _gz(tmp_path, data: bytes):
    import gzip
    d = tmp_path / "-work-repo"
    d.mkdir()
    raw = gzip.compress(data, mtime=0)
    return d / "s.jsonl.gz", raw


def test_a_corrupt_gzip_transcript_is_skipped_and_counted_not_a_crash(tmp_path):
    import gzip
    import zlib
    f, raw = _gz(tmp_path, _entries(50).encode())
    bad = bytearray(raw)
    bad[20] ^= 0xFF                                       # inside the deflate stream
    f.write_bytes(bytes(bad))
    with pytest.raises(zlib.error):                       # the damage this test is about: zlib.error, not OSError
        gzip.decompress(bytes(bad))
    refused: list[dict] = []
    evs, skipped = phases.events_from_transcripts(tmp_path, skipped_files=refused)
    assert evs == [] and skipped == 1
    assert refused == [{"path": "-work-repo/s.jsonl.gz", "reason": "corrupt", "kept_lines": 0}]


def test_a_truncated_gzip_transcript_keeps_the_lines_read_before_the_cut_and_counts_the_cut(tmp_path):
    f, raw = _gz(tmp_path, _entries(50).encode())
    f.write_bytes(raw[: len(raw) * 3 // 4])
    refused: list[dict] = []
    evs, skipped = phases.events_from_transcripts(tmp_path, skipped_files=refused)
    assert 0 < len(evs) < 50 and skipped == 1
    assert [e["t"] - evs[0]["t"] for e in evs] == list(range(len(evs)))      # the first entries, in order
    assert refused == [{"path": "-work-repo/s.jsonl.gz", "reason": "truncated", "kept_lines": len(evs)}]


def test_a_transcript_over_the_decompressed_size_cap_is_cut_there_and_counted(tmp_path, monkeypatch):
    d = tmp_path / "-work-repo"
    d.mkdir()
    text = _entries(10)
    (d / "s.jsonl").write_text(text)
    first_line = len(text.splitlines(keepends=True)[0])
    monkeypatch.setattr(phases, "TRANSCRIPT_CHAR_CAP", first_line * 3 + 1)
    refused: list[dict] = []
    evs, skipped = phases.events_from_transcripts(tmp_path, skipped_files=refused)
    assert len(evs) == 3 and skipped == 1
    assert refused == [{"path": "-work-repo/s.jsonl", "reason": "over-size-cap", "kept_lines": 3}]


def test_wrongly_shaped_entries_are_counted_as_skipped_and_do_not_break_classification(tmp_path):
    d = tmp_path / "-work-repo"
    d.mkdir()
    (d / "s.jsonl").write_text("".join(json.dumps(e) + "\n" for e in [
        {"type": "user", "timestamp": _at(0), "message": {"content": [{"type": "text", "text": 5}]}},
        {"type": "assistant", "timestamp": _at(1), "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "Bash", "input": ["uv run pytest"]}]}},
        {"type": "assistant", "timestamp": _at(2), "message": {"content": [
            {"type": "tool_use", "id": "b", "name": "Write", "input": {"file_path": ["src/a.py"]}}]}},
        {"type": "assistant", "timestamp": _at(3), "message": {"content": [
            {"type": "tool_use", "id": "c", "name": "Read", "input": {"file_path": "src/a.py"}}]}},
        {"type": "assistant", "timestamp": _at(9), "message": {"content": []}}]))
    evs, skipped = phases.events_from_transcripts(tmp_path)
    assert skipped == 3 and len(evs) == 5                 # every timestamp is kept as an event
    assert all(isinstance(e["input"], dict) for e in evs)
    assert sum(phases.classify(evs, RULES, [])["seconds"].values()) == 9


def test_classify_tolerates_a_non_dict_input_and_a_non_string_path():
    evs = [ev(0, "Bash", input=["ls"]), ev(1, "Write", input={"file_path": 7}), ev(3, kind="other")]
    s = phases.classify(evs, RULES, [])["seconds"]
    assert s["understand"] == 1 and s["implement"] == 2


def test_damaged_transcript_files_are_named_in_common_phases(tmp_path):
    d = _step_with_transcript(tmp_path, [_prompt(0, "build it"), _tool(0, "Read", {}), _tool(10, "Read", {})],
                              turns=[("arm-a1-001", "build it", 10_000, 1.0)])
    import gzip
    raw = gzip.compress(_entries(50).encode(), mtime=0)
    (d / "transcripts" / "a1" / "-work-repo" / "s.jsonl.gz").write_bytes(raw[: len(raw) * 3 // 4])
    v = phases.common_phases(d, [], RULES)["value"]
    assert v["skipped_lines"] == 1
    assert [(x["path"], x["reason"]) for x in v["skipped_files"]] == [("-work-repo/s.jsonl.gz", "truncated")]


def test_the_mini_steps_classified_seconds_add_up_to_its_arm_time():
    from runner.scoring import evidence
    step = MINI / "alpha" / "02"
    s = phases.common_phases(step, [], RULES)["value"]["seconds"]
    arm = evidence.arm_time(step)["value"]["seconds"]
    assert abs(sum(v for p, v in s.items() if p != "waiting") - arm) <= 0.5


@pytest.mark.parametrize("cmd", ['git commit -m "fix ruff warnings"', "grep -rn pytest src",
                                 "cat <<'EOF'\nimport pytest\nEOF", "cat /tmp/pytest.out", "uv add --dev pytest",
                                 "pgrep -af pytest"])
def test_a_test_tool_named_outside_command_position_is_not_a_test_run(cmd):
    assert not phases.is_test_command(cmd, RULES)


@pytest.mark.parametrize("cmd", ["uv run pytest -q", "cd /work/r; uv run pytest -q 2>&1 | tail -3",
                                 "uv run ruff check . && uv run mypy --strict .", "python -m pytest tests",
                                 "PYTHONPATH=src timeout 60 .venv/bin/python -m pytest",
                                 "uv run --no-project --with pytest python -m pytest",
                                 "for i in 1 2; do uv run pytest -x; done", "(uv run pytest)",
                                 "uv run troupe config show a"])
def test_a_test_tool_in_command_position_is_a_test_run(cmd):
    assert phases.is_test_command(cmd, RULES)


def test_a_command_merely_mentioning_a_test_tool_neither_counts_as_testing_nor_clears_rework():
    for cmd in ('git commit -m "fix ruff warnings"', "grep pytest src/a.py", "cat <<'EOF'\nimport pytest\nEOF"):
        evs = [_bash(0, "uv run pytest", id="b1"), ev(1, kind="result", id="b1", output="1 failed"),
               _bash(1, cmd, id="b2"), ev(2, kind="result", id="b2", output="0 failed? no: ok"),
               ev(2, "Write", input={"file_path": "src/a.py"}), ev(4, kind="other")]
        s = phases.classify(evs, RULES, [])["seconds"]
        assert s["test"] == 1 and s["rework"] == 2, cmd


def test_write_calls_only_count_inside_python_code_and_heredocs_are_parsed_in_every_shape():
    t = phases.bash_write_targets
    assert t("git commit -m \"use open(p, 'w') now\"", RULES) is None          # code in a commit message
    assert t("cat > /tmp/x <<'EOF'\nopen('src/a.py','w')\nEOF", RULES) is None   # a heredoc that is not python
    assert t('[[ "$a" > b ]] && echo y', RULES) is None                        # a [[ ]] string comparison
    assert t("(( a > b )) && echo y", RULES) is None                           # an arithmetic comparison
    assert t("python3 - <<'EOF'\nif a > b:", RULES) is None                    # unterminated heredoc
    assert t("cat > src/p.py <<EOF\nEOF\necho x > src/q.py\ncat > src/r.py <<EOF\nbody\nEOF",
             RULES) == ["src/p.py", "src/q.py", "src/r.py"]                    # an empty-body heredoc
    assert t("python3 -c \"open('src/c.py','w').write('x')\"", RULES) == ["src/c.py"]
    assert t("cat <<'EOF' | python3\nopen('src/d.py','w').write(s)\nEOF", RULES) == ["src/d.py"]
    assert t("uv run python - <<'EOF'\nPath('src/e.py').write_text(s)\nEOF", RULES) == ["src/e.py"]
    assert t('cat <<< "x"; echo y > src/f.py', RULES) == ["src/f.py"]          # a here-string is not a heredoc


def test_a_heredoc_saved_to_a_script_counts_as_code_only_when_the_same_call_runs_that_script():
    t = phases.bash_write_targets
    body = "cat > /tmp/patch.py <<'EOF'\np='src/troupe/store.py'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF\n"
    assert t(body + "python3 /tmp/patch.py && git diff --stat", RULES) == ["src/troupe/store.py"]   # pass1 superpowers/04
    assert t(body + "cd /work/r && uv run python /tmp/patch.py", RULES) == ["src/troupe/store.py"]
    assert t(body + "echo saved", RULES) is None                              # saved, never run here
    assert t(body + "python3 /tmp/other.py", RULES) is None                   # a different script runs


@pytest.mark.parametrize("cmd", [
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run([\"uv\",\"run\",\"pytest\",\"tests/t.py\",\"-q\"])\nEOF",
    "uv run python -c \"import sys, pytest; sys.exit(pytest.main(['-q', 'tests/t.py']))\"",
    "cat > /tmp/mut.py <<'EOF'\nimport subprocess\nsubprocess.run(['uv', 'run', 'pytest', '-x'])\nEOF\npython3 /tmp/mut.py"])
def test_a_test_run_driven_from_python_code_the_call_runs_is_a_test_run(cmd):
    assert phases.is_test_command(cmd, RULES)


def test_a_test_run_inside_python_code_that_is_only_saved_is_not_a_test_run():
    assert not phases.is_test_command("cat > tests/run.py <<'EOF'\nimport pytest\npytest.main(['-q'])\nEOF", RULES)


# --- fix round 5: heredoc operators only at shell level; tee-saved scripts; ${...} ---------------------------------

@pytest.mark.parametrize("cmd", ['grep -n "<<EOF" scripts/x.sh\nuv run pytest -q',
                                 'python3 -c "print(1 << n)"\nuv run pytest -q',
                                 "echo $(( a << b ))\nuv run pytest -q",
                                 "(( x = a << b ))\nuv run pytest -q",
                                 "echo '<<EOF'\nuv run pytest -q"])
def test_a_heredoc_operator_inside_quotes_or_arithmetic_does_not_swallow_the_rest_of_the_command(cmd):
    assert phases.is_test_command(cmd, RULES)


def test_a_quoted_heredoc_operator_does_not_hide_a_later_write():
    assert phases.bash_write_targets('grep -n "<<EOF" x.sh\necho y > src/f.py', RULES) == ["src/f.py"]
    assert phases.bash_write_targets("python3 - <<'EOF'\nif a > b:", RULES) is None    # genuine unterminated: kept


def test_a_script_saved_with_tee_and_then_run_is_code():
    body = "tee /tmp/p.py >/dev/null <<'EOF'\nopen('src/t.py','w').write(s)\nEOF\n"
    assert phases.bash_write_targets(body + "python3 /tmp/p.py", RULES) == ["src/t.py"]
    assert phases.bash_write_targets(body + "echo saved", RULES) is None


def test_saved_script_detection_follows_the_write_commands_rules():
    import dataclasses
    no_redirects = dataclasses.replace(RULES, write_commands=tuple(
        r for r in RULES.write_commands if not r.pattern.startswith("(?<![0-9&<>])>")))
    cmd = "cat > /tmp/p.py <<'EOF'\nopen('src/t.py','w').write(s)\nEOF\npython3 /tmp/p.py"
    assert phases.bash_write_targets(cmd, RULES) == ["src/t.py"]
    assert phases.bash_write_targets(cmd, no_redirects) is None      # no redirect rule: nothing saved, nothing run


def test_a_parameter_expansion_brace_does_not_split_a_command():
    assert not phases.is_test_command("echo ${d} pytest", RULES)
    assert phases.is_test_command("cd ${d} && uv run pytest", RULES)


def test_an_apostrophe_in_a_shell_comment_does_not_hide_a_later_heredoc():
    # pass1 speckit/04: "# deliberate break: print the current command's actor" preceded a python heredoc edit
    cmd = ("uv run pytest -q\n# the command's actor\n"
           "python3 - <<'EOF'\np='src/troupe/config/commands.py'; s=open(p).read()\nopen(p,'w').write(s)\nEOF")
    assert phases.bash_write_targets(cmd, RULES) == ["src/troupe/config/commands.py"]
    assert phases.bash_write_targets("echo a#b > src/x.py", RULES) == ["src/x.py"]      # '#' inside a word
