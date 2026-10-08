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
    assert killed == {"stem": "arm-a2-002", "seconds": 90.0, "usd": None, "killed": True, "time_source": "transcript"}
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


def test_without_a_run_record_and_without_questions_the_questions_are_missing(tmp_path):
    m = evidence.questions(tmp_path)
    assert values.is_missing(m) and m["missing"].endswith("questions.jsonl")


def test_with_a_run_record_an_absent_questions_file_means_the_arm_asked_none(tmp_path):
    (tmp_path / "run.json").write_text('{"outcome": "done"}')
    v = evidence.questions(tmp_path)["value"]
    assert v["items"] == [] and v["skipped_lines"] == 0 and v["discovery"] == "absent"


def test_a_malformed_question_line_is_skipped_and_counted_and_the_rest_kept(tmp_path):
    (tmp_path / "questions.jsonl").write_text('{"n": 1, "kind": "x"}\nnot json\n{"n": 2, "kind": "y"}\n')
    v = evidence.questions(tmp_path)["value"]
    assert [q["n"] for q in v["items"]] == [1, 2] and v["skipped_lines"] == 1


def test_an_absent_discovery_questions_file_is_reported_absent_not_an_error(tmp_path):
    (tmp_path / "questions.jsonl").write_text('{"n": 1}\n')
    v = evidence.questions(tmp_path)["value"]
    assert v["discovery"] == "absent" and [q["run"] for q in v["items"]] == ["b"]


def test_without_a_usable_transcript_a_turn_woken_by_background_agents_sums_all_its_result_line_durations(tmp_path):
    # R9: each wake of the main loop ends in its own result line; the cumulative cost is the last one's.
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0),
              _res(duration_ms=4000, total_cost_usd=2.0) + _res(duration_ms=500, total_cost_usd=2.5)
              + _res(duration_ms=2500, total_cost_usd=3.0))
    t = evidence.arm_time(d)["value"]
    assert [x["seconds"] for x in t["turns"]] == [1.0, 7.0] and t["seconds"] == 8.0
    assert t["turns"][1]["usd"] == 2.0


def test_without_a_usable_transcript_one_result_line_lacking_duration_makes_the_step_time_missing(tmp_path):
    d = _step(tmp_path, _res(duration_ms=4000, total_cost_usd=2.0) + _res(total_cost_usd=3.0))
    m = evidence.arm_time(d)
    assert values.is_missing(m) and "arm-a1-001" in m["why"]


def test_an_unknown_cost_on_the_last_result_line_leaves_usd_unknown(tmp_path):
    d = _step(tmp_path, _res(duration_ms=4000, total_cost_usd=2.0) + _res(duration_ms=1000),
              _res(duration_ms=1000, total_cost_usd=5.0))
    t = evidence.arm_time(d)["value"]["turns"]
    assert t[0]["usd"] is None and t[0]["seconds"] == 5.0 and t[1]["usd"] == 5.0 and t[1]["absorbs_previous"]


def _transcript(d, rel_path, entries):
    p = d / "transcripts" / "a1" / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e) + "\n" for e in entries))


def _ts(sec):
    return f"2026-10-05T09:{sec // 60:02d}:{sec % 60:02d}.000Z"


def test_a_turns_time_is_its_transcript_span_from_the_first_queue_operation_including_background_agents(tmp_path):
    # R12: the main loop's result line says 10 s, but a background subagent kept working until 100 s.
    d = _step(tmp_path, _res(duration_ms=10_000, total_cost_usd=1.0))
    _transcript(d, "-work-repo/s.jsonl", [
        {"type": "queue-operation", "timestamp": _ts(0)},
        {"type": "user", "timestamp": _ts(3), "message": {"content": "build it"}},
        {"type": "assistant", "timestamp": _ts(13), "message": {"content": [{"type": "text", "text": "started"}]}}])
    _transcript(d, "-work-repo/s/subagents/agent-1.jsonl", [
        {"type": "user", "isSidechain": True, "timestamp": _ts(14), "message": {"content": "do part"}},
        {"type": "assistant", "isSidechain": True, "timestamp": _ts(100), "message": {"content": []}}])
    t = evidence.arm_time(d)["value"]
    assert t["turns"] == [{"stem": "arm-a1-001", "seconds": 100.0, "usd": 1.0, "time_source": "transcript"}]
    assert t["seconds"] == 100.0


def test_a_turn_without_a_usable_transcript_falls_back_to_its_summed_durations(tmp_path):
    d = _step(tmp_path, _res(duration_ms=4000, total_cost_usd=1.0) + _res(duration_ms=1000, total_cost_usd=1.5))
    t = evidence.arm_time(d)["value"]
    assert t["turns"] == [{"stem": "arm-a1-001", "seconds": 5.0, "usd": 1.5, "time_source": "duration_ms"}]


def test_a_turn_whose_stderr_shows_the_background_wait_ceiling_is_flagged(tmp_path):
    # R13: the CLI waited up to 600 s on background shell tasks that leave no transcript entries.
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0), _res(duration_ms=1000, total_cost_usd=2.0))
    with gzip.open(d / "turns" / "arm-a1-001.stderr.gz", "wt") as f:
        f.write("Background tasks still running after 600s; terminating. Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0\n")
    (d / "turns" / "arm-a1-002.stderr.gz").write_bytes(b"not gzip")          # unreadable: no flag, no failure
    turns = evidence.arm_time(d)["value"]["turns"]
    assert turns[0]["background_wait"] is True and "background_wait" not in turns[1]


def _flipped_gz(p, text):
    raw = bytearray(gzip.compress(text.encode(), mtime=0))
    raw[20] ^= 0xFF                                       # inside the deflate stream: reading raises zlib.error
    p.write_bytes(bytes(raw))


def test_a_corrupt_gzip_turn_stream_reads_as_unreadable_not_a_crash(tmp_path):
    import zlib
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0))
    p = d / "turns" / "arm-a1-001.stream.jsonl.gz"
    _flipped_gz(p, "".join(json.dumps(_res(duration_ms=i)[0]) + "\n" for i in range(200)))
    try:
        gzip.decompress(p.read_bytes())
        raise AssertionError("the fixture is meant to be corrupt")
    except zlib.error:
        pass
    assert evidence._result_lines(p) is None
    m = evidence.arm_time(d)                               # unreadable stream, no transcript: missing, not a crash
    assert values.is_missing(m) and "arm-a1-001" in m["why"]


def test_a_corrupt_gzip_stderr_gives_no_background_wait_flag_and_no_crash(tmp_path):
    d = _step(tmp_path, _res(duration_ms=1000, total_cost_usd=1.0))
    _flipped_gz(d / "turns" / "arm-a1-001.stderr.gz", "noise\n" * 500 + "Background tasks still running after 600s\n")
    assert "background_wait" not in evidence.arm_time(d)["value"]["turns"][0]


def test_arm_time_reads_the_transcripts_once_even_with_a_killed_turn(monkeypatch):
    from runner.scoring import phases
    calls = []
    real = phases.events_from_transcripts
    monkeypatch.setattr(phases, "events_from_transcripts", lambda *a, **k: calls.append(a) or real(*a, **k))
    t = evidence.arm_time(MINI / "alpha" / "02")["value"]
    assert t["turns"][-1]["killed"] and t["turns"][-1]["seconds"] == 90.0 and len(calls) == 1


def test_an_existing_but_unreadable_questions_file_is_missing_not_asked_none(tmp_path):
    (tmp_path / "run.json").write_text('{"outcome": "done"}')
    (tmp_path / "questions.jsonl").mkdir()                       # exists, but reading it fails (IsADirectoryError)
    m = evidence.questions(tmp_path)
    assert values.is_missing(m) and "unreadable" in m["why"]


def test_a_questions_file_that_is_not_utf8_is_missing_not_asked_none(tmp_path):
    (tmp_path / "run.json").write_text('{"outcome": "done"}')
    (tmp_path / "questions.jsonl").write_bytes(b'{"n": 1}\n\xff\xfe\n')
    m = evidence.questions(tmp_path)
    assert values.is_missing(m) and "unreadable" in m["why"]


def test_a_json_file_that_is_not_utf8_is_missing_not_a_crash(tmp_path):
    (tmp_path / "run.json").write_bytes(b'{"outcome": "\xff"}')
    m = evidence.read_json(tmp_path / "run.json")
    assert values.is_missing(m) and m["why"].startswith("unreadable")


# --- R36: reported, not scored ---------------------------------------------------------------------------------------

def _jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_owner_review_time_sums_owner_seconds_split_into_gates_and_escalations(tmp_path):
    (tmp_path / "run.json").write_text('{"outcome": "done"}')
    _jsonl(tmp_path / "questions.jsonl", [{"n": 1, "kind": "approval", "owner_seconds": 10.0},
                                          {"n": 2, "kind": "question", "owner_seconds": 5.5},
                                          {"n": 3, "kind": "next_command", "owner_seconds": 0.0}])
    v = evidence.owner_review(tmp_path)["value"]
    assert v == {"seconds": 15.5, "gates": 1, "gate_seconds": 10.0, "escalation_seconds": 5.5}


def test_owner_review_time_is_zero_with_a_run_and_no_questions_and_missing_without_a_run(tmp_path):
    assert values.is_missing(evidence.owner_review(tmp_path))
    (tmp_path / "run.json").write_text('{"outcome": "done"}')
    assert evidence.owner_review(tmp_path)["value"]["seconds"] == 0.0


def test_tracker_reads_the_snapshot_and_step_6s_round_trip(tmp_path):
    (tmp_path / "tracker.json").write_text(json.dumps({"backend": "github", "initialised": True,
                                                       "survives_restore": True, "issues": [{"n": 1}, {"n": 2}]}))
    rt = {"issue": "o/r#5", "state": "closed", "comments": 1, "commits_referencing": ["abc"],
          "issue_links_commit": True, "non_py_files_changed": ["spec.md"]}
    (tmp_path / "tracker-round-trip.json").write_text(json.dumps(rt))
    v = evidence.tracker(tmp_path)["value"]
    assert v == {"backend": "github", "initialised": True, "survives_restore": True, "issues": 2, "round_trip": rt}
    (tmp_path / "tracker-round-trip.json").unlink()
    assert evidence.tracker(tmp_path)["value"]["round_trip"] is None


def test_discovery_reads_why_n_a_stopped_and_is_missing_without_a_record(tmp_path):
    assert values.is_missing(evidence.discovery(tmp_path))
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "discovery.json").write_text(json.dumps(
        {"outcome": "discovery-stop", "discovery": {"why": "code", "turn": 4}, "exchanges": 4}))
    assert evidence.discovery(tmp_path)["value"] == {"outcome": "discovery-stop", "why": "code", "turn": 4,
                                                     "exchanges": 4}


def test_runs_reads_attempts_interventions_harness_faults_and_park(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({
        "outcome": "done", "attempts": 2, "interventions": ["owner-shell-commit:abc"], "park": None,
        "harness_faults": [{"kind": "infra-hidden", "signature": "pytest exit", "action": "rerun", "run": "b",
                            "attempt": 1, "detail": "x"}]}))
    v = evidence.runs(tmp_path)["value"]
    assert v == {"attempts": 2, "interventions": ["owner-shell-commit:abc"], "parked": False,
                 "harness_faults": [{"kind": "infra-hidden", "signature": "pytest exit", "action": "rerun",
                                     "run": "b", "attempt": 1}]}


# --- R38: arm-level violations (results/<pass>/<arm>/arm-violations.jsonl) ---------------------------------------

def _arm_file(tmp_path, text: str | bytes):
    d = tmp_path / "arm"
    d.mkdir(exist_ok=True)
    (d / "arm-violations.jsonl").write_bytes(text if isinstance(text, bytes) else text.encode())
    return d


def _jl(*recs):
    return "".join(json.dumps(r) + "\n" for r in recs)


def test_a_missing_arm_violations_file_means_none_not_unmeasured(tmp_path):
    (tmp_path / "arm").mkdir()
    r = evidence.arm_violations(tmp_path / "arm")
    assert r["value"] == [] and not values.is_missing(r)


def test_an_unreadable_arm_violations_file_is_unmeasured_not_zero(tmp_path):
    for bad in (b"\xff\xfe not utf-8\n", '{"kind": "setup-drift"}\n{not json\n', '["not", "an object"]\n'):
        r = evidence.arm_violations(_arm_file(tmp_path, bad))
        assert values.is_missing(r), bad


def test_a_directory_where_the_file_should_be_is_unmeasured(tmp_path):
    d = tmp_path / "arm"
    (d / "arm-violations.jsonl").mkdir(parents=True)
    assert values.is_missing(evidence.arm_violations(d))


def test_discovery_run_a_entries_are_dropped(tmp_path):
    d = _arm_file(tmp_path, _jl({"step": 1, "run": "a", "kind": "own-token-in-evidence"},
                                {"step": 1, "run": "b", "kind": "own-token-in-evidence"}))
    assert [v["run"] for v in evidence.arm_violations(d)["value"]] == ["b"]


def test_setup_drift_is_deduped_by_step_run_and_check(tmp_path):
    d = _arm_file(tmp_path, _jl(
        {"step": 2, "run": "b", "kind": "setup-drift", "check": "common.origin", "after_restore": False},
        {"step": 2, "run": "b", "kind": "setup-drift", "check": "common.origin", "after_restore": True},   # same drift
        {"step": 2, "run": "b", "kind": "setup-drift", "check": "common.git-identity"},                    # another check
        {"step": 3, "run": "b", "kind": "setup-drift", "check": "common.origin"}))                         # another step
    got = [(v["step"], v["check"]) for v in evidence.arm_violations(d)["value"]]
    assert got == [(2, "common.origin"), (2, "common.git-identity"), (3, "common.origin")]


def test_other_kinds_are_deduped_by_step_run_and_kind(tmp_path):
    d = _arm_file(tmp_path, _jl(
        {"step": 2, "run": "b", "kind": "own-token-in-evidence", "files": ["x"]},
        {"step": 2, "run": "b", "kind": "own-token-in-evidence", "files": ["x", "y"]},     # a re-scan of the same step
        {"step": 2, "run": "b", "kind": "link-in-home", "path": "/h/.config"},             # another kind
        {"step": 2, "run": "c", "kind": "own-token-in-evidence", "files": ["x"]}))         # another run
    got = [(v["run"], v["kind"]) for v in evidence.arm_violations(d)["value"]]
    assert got == [("b", "own-token-in-evidence"), ("b", "link-in-home"), ("c", "own-token-in-evidence")]


def test_stepless_runless_repairs_are_never_deduped_a_same_path_repeat_counts_twice(tmp_path):
    """The checklist's link-in-home repairs are one-shot: a repeat on the same path means the arm re-created the link."""
    d = _arm_file(tmp_path, _jl({"kind": "link-in-home", "path": "/h/.config"},
                                {"kind": "link-in-home", "path": "/h/.config/gh/hosts.yml"},
                                {"kind": "link-in-home", "path": "/h/.config"}))
    assert [v["path"] for v in evidence.arm_violations(d)["value"]] == [
        "/h/.config", "/h/.config/gh/hosts.yml", "/h/.config"]


def test_an_unhashable_dedupe_field_is_a_corrupt_record_so_unmeasured(tmp_path):
    for rec in ({"step": [1], "run": "b", "kind": "setup-drift", "check": "c"},
                {"step": 1, "run": {"x": 1}, "kind": "own-token-in-evidence"},
                {"step": 1, "run": "b", "kind": ["setup-drift"]},
                {"step": 1, "run": "b", "kind": "setup-drift", "check": ["c"]}):
        r = evidence.arm_violations(_arm_file(tmp_path, _jl(rec)))
        assert values.is_missing(r) and "corrupt" in r["why"], rec
