import gzip, json, os, subprocess, sys
from pathlib import Path

from runner import config
import threading

from runner import transcripts
from runner.transcripts import snapshot, collect, verify_pin, safe_files, MAX_FILE_BYTES

FAKE_CLAUDE = Path(__file__).resolve().parents[2] / "runner" / "images" / "dryrun" / "fake_claude.py"


def w(p, *objs):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(o) + "\n" for o in objs))

def asst(m): return {"type": "assistant", "message": {"model": m, "content": []}}

def gz(p, *objs):
    with gzip.open(p, "wt") as fh:
        fh.write("".join(json.dumps(o) + "\n" for o in objs))
    return p

INIT_OK = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "claude_code_version": "2.1.281"}


# --- collection -------------------------------------------------------------------------------------------

def test_collect_includes_new_subagent_transcripts_only(tmp_path):
    cfg = tmp_path / ".claude"
    w(cfg / "projects/p/old.jsonl", asst("claude-opus-5-5"))
    before = snapshot(cfg)
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    w(cfg / "projects/p/s1/subagents/agent-1.jsonl", asst("claude-opus-5-5"))
    assert sorted(p.name for p in collect(cfg, before, tmp_path / "out")) == ["agent-1.jsonl.gz", "s1.jsonl.gz"]

def test_collect_includes_a_changed_transcript_and_keeps_its_relative_path(tmp_path):
    # --resume appends to the same <session>.jsonl, so "changed" matters as much as "new".
    cfg = tmp_path / ".claude"
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    before = snapshot(cfg)
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"), asst("claude-opus-5-5"))
    out = collect(cfg, before, tmp_path / "out")
    assert out == [tmp_path / "out" / "p" / "s1.jsonl.gz"]
    assert gzip.open(out[0], "rt").read().count("\n") == 2

def test_collect_with_no_projects_dir_is_empty(tmp_path):
    assert snapshot(tmp_path / ".claude") == {}
    assert collect(tmp_path / ".claude", {}, tmp_path / "out") == []


# --- symlink safety (review S-1 extension: the arm controls this tree) ------------------------------------

def test_symlinks_in_the_arm_tree_are_never_followed(tmp_path):            # review S-1 extension
    secret = tmp_path / "host-secret.jsonl"; secret.write_text("private\n")
    root = tmp_path / ".claude" / "projects" / "p"; root.mkdir(parents=True)
    os.symlink(secret, root / "evil.jsonl")
    assert safe_files(tmp_path / ".claude" / "projects") == []

def test_a_symlink_to_a_host_file_is_skipped_recorded_and_never_copied(tmp_path):
    secret = tmp_path / "host-secret.jsonl"; secret.write_text('{"secret": "HOST-PRIVATE"}\n')
    cfg = tmp_path / ".claude"
    before = snapshot(cfg)
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    os.symlink(secret, cfg / "projects/p/evil.jsonl")
    skipped: list[dict] = []
    out = collect(cfg, before, tmp_path / "out", skipped=skipped)
    assert [p.name for p in out] == ["s1.jsonl.gz"]
    assert skipped == [{"path": "p/evil.jsonl", "reason": "symlink"}]
    record = json.loads((tmp_path / "out" / "unsafe-entries.json").read_text())
    assert record == skipped
    for f in (tmp_path / "out").rglob("*"):
        if f.suffix == ".gz":
            assert "HOST-PRIVATE" not in gzip.open(f, "rt").read()

def test_a_symlinked_directory_pointing_outside_is_not_walked(tmp_path):
    outside = tmp_path / "host-dir"; w(outside / "x.jsonl", asst("claude-opus-5-5"))
    root = tmp_path / ".claude" / "projects"; root.mkdir(parents=True)
    os.symlink(outside, root / "p")
    skipped: list[dict] = []
    assert safe_files(root, skipped=skipped) == []
    assert skipped == [{"path": "p", "reason": "symlink"}]

def test_a_symlink_inside_the_tree_is_skipped_too(tmp_path):
    root = tmp_path / ".claude" / "projects"
    w(root / "p/real.jsonl", asst("claude-opus-5-5"))
    os.symlink(root / "p/real.jsonl", root / "p/alias.jsonl")
    assert safe_files(root) == [root / "p/real.jsonl"]

def test_a_projects_root_that_is_itself_a_symlink_is_rejected(tmp_path):
    outside = tmp_path / "host-dir"; w(outside / "p/x.jsonl", asst("claude-opus-5-5"))
    cfg = tmp_path / ".claude"; cfg.mkdir()
    os.symlink(outside, cfg / "projects")
    skipped: list[dict] = []
    assert safe_files(cfg / "projects", skipped=skipped) == []
    assert skipped == [{"path": ".", "reason": "symlink"}]
    assert snapshot(cfg) == {}
    assert collect(cfg, {}, tmp_path / "out") == []

def test_a_fifo_is_skipped_by_the_walk(tmp_path):
    root = tmp_path / ".claude" / "projects" / "p"; root.mkdir(parents=True)
    os.mkfifo(root / "pipe.jsonl")
    skipped: list[dict] = []
    assert safe_files(root.parent, skipped=skipped) == []
    assert skipped == [{"path": "p/pipe.jsonl", "reason": "not-regular"}]

def test_a_hardlinked_file_is_skipped(tmp_path):
    # A hard link has no symlink to detect; a transcript Claude Code wrote has exactly one link.
    elsewhere = tmp_path / "elsewhere.jsonl"; w(elsewhere, asst("claude-opus-5-5"))
    root = tmp_path / ".claude" / "projects" / "p"; root.mkdir(parents=True)
    os.link(elsewhere, root / "linked.jsonl")
    skipped: list[dict] = []
    assert safe_files(root.parent, skipped=skipped) == []
    assert skipped == [{"path": "p/linked.jsonl", "reason": "hardlinked"}]


# --- pin verification -------------------------------------------------------------------------------------

def test_subagent_on_another_model_is_a_violation(tmp_path):
    f = tmp_path / "agent-1.jsonl"; w(f, asst("claude-opus-5-5"), asst("claude-haiku-4-5"))
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.violations == [{"file": str(f), "line": 2, "where": "assistant", "model": "claude-haiku-4-5"}]

def test_synthetic_messages_are_counted_not_faulted(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("<synthetic>"), asst("claude-opus-5-5"))
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert r.ok and r.synthetic == 1 and r.assistant_messages == 2

def test_stream_assistant_events_and_model_usage_are_checked(tmp_path):     # review C-6
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-sonnet-5"),
           {"type": "result", "modelUsage": {"claude-opus-5-5": {}, "claude-haiku-4-5": {}}})
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert [v["where"] for v in r.violations] == ["stream.assistant", "result.modelUsage"]

def test_the_init_model_is_checked(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {**INIT_OK, "model": "claude-sonnet-5"})
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and r.violations == [{"file": str(s), "line": 1, "where": "init", "model": "claude-sonnet-5"}]

def test_streams_alone_are_not_evidence_for_an_arm_step(tmp_path):         # review C-6
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([], [s], config.load_pins(), unsafe=[])
    assert not r.ok and r.no_evidence

def test_a_wrong_claude_code_version_is_a_violation(tmp_path):             # review C-16
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {**INIT_OK, "claude_code_version": "2.1.290"})
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert r.violations == [{"file": str(s), "line": 1, "where": "claude_code_version", "model": "2.1.290"}]

def test_a_truncated_last_line_is_counted_not_fatal(tmp_path):             # review C-6
    f = tmp_path / "s.jsonl"; f.write_text(json.dumps(asst("claude-opus-5-5")) + "\n" + '{"type": "assi')
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert r.ok and r.truncated_lines == 1

def test_an_oversize_marker_is_acceptable_only_on_a_timeout_or_no_result_turn(tmp_path):
    # session.py writes {"type": "bk_oversize_line"} in place of a stream line over its reader limit.
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"), {"type": "bk_oversize_line", "bytes": 99})
    for outcome in ("timeout", "no_result"):
        r = verify_pin([t], [s], config.load_pins(), unsafe=[], stream_outcomes={s: outcome})
        assert r.ok and r.truncated_lines == 1, outcome
    for outcomes in ({s: "ok"}, {s: "is_error"}, None):
        r = verify_pin([t], [s], config.load_pins(), unsafe=[], stream_outcomes=outcomes)
        assert not r.ok and r.violations == [{"file": str(s), "line": 3, "where": "oversize_marker", "model": "<uninspected>"}]


# --- fix round 1: only the final line may be truncated; hostile shapes never raise ---------------------

def test_an_undecodable_line_that_is_not_the_last_is_a_violation(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(asst("claude-opus-5-5")) + "\n" + '{"type": "assi\n' + json.dumps(asst("claude-opus-5-5")) + "\n")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.violations == [{"file": str(f), "line": 2, "where": "unreadable_line", "model": "<uninspected>"}]

def test_a_non_object_line_is_a_violation(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text(json.dumps(asst("claude-opus-5-5")) + "\n[1, 2]\n" + json.dumps(asst("claude-opus-5-5")) + "\n")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and [v["where"] for v in r.violations] == ["unreadable_line"]

def test_a_truncated_final_stream_line_is_counted_not_fatal(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = tmp_path / "t.stream.jsonl.gz"
    with gzip.open(s, "wt") as fh:
        fh.write(json.dumps(INIT_OK) + "\n" + json.dumps(asst("claude-opus-5-5")) + "\n" + '{"typ')
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert r.ok and r.truncated_lines == 1

def test_an_overlong_line_is_never_held_whole_and_is_a_violation(tmp_path, monkeypatch):
    monkeypatch.setattr(transcripts, "MAX_LINE_BYTES", 1024)
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(asst("claude-opus-5-5")) + "\n" + json.dumps(asst("x" * 5000)) + "\n" + json.dumps(asst("claude-opus-5-5")) + "\n")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.assistant_messages == 2
    assert r.violations == [{"file": str(f), "line": 2, "where": "oversize_line", "model": "<uninspected>"}]

HOSTILE = [
    ("message is a string", {"type": "assistant", "message": "claude-opus-5-5"}, "assistant", "<malformed:str>"),
    ("message is a list", {"type": "assistant", "message": ["claude-opus-5-5"]}, "assistant", "<malformed:list>"),
    ("model missing", {"type": "assistant", "message": {"content": []}}, "assistant", "<missing>"),
    ("model is a dict", {"type": "assistant", "message": {"model": {"id": "claude-opus-5-5"}}}, "assistant", "<malformed:dict>"),
    ("model is a list", {"type": "assistant", "message": {"model": ["claude-opus-5-5"]}}, "assistant", "<malformed:list>"),
    ("model is a number", {"type": "assistant", "message": {"model": 5}}, "assistant", "<malformed:int>"),
]

def test_hostile_transcript_shapes_are_violations_never_exceptions(tmp_path):
    for name, line, where, model in HOSTILE:
        f = tmp_path / "s.jsonl"; w(f, asst("claude-opus-5-5"), line)
        r = verify_pin([f], [], config.load_pins(), unsafe=[])
        assert not r.ok and r.violations == [{"file": str(f), "line": 2, "where": where, "model": model}], name

STREAM_HOSTILE = [
    ("stream message not a dict", {"type": "assistant", "message": 7}, "stream.assistant", "<malformed:int>"),
    ("init model a dict", {**INIT_OK, "model": {"x": 1}}, "init", "<malformed:dict>"),
    ("init model missing", {k: v for k, v in INIT_OK.items() if k != "model"}, "init", "<missing>"),
    ("init version a list", {**INIT_OK, "claude_code_version": ["2.1.281"]}, "claude_code_version", "<malformed:list>"),
    ("modelUsage a list", {"type": "result", "modelUsage": ["claude-opus-5-5"]}, "result.modelUsage", "<malformed:list>"),
    ("modelUsage a string", {"type": "result", "modelUsage": "claude-opus-5-5"}, "result.modelUsage", "<malformed:str>"),
    ("type a dict", {"type": {"a": 1}, "message": {"model": "x"}}, None, None),
]

def test_hostile_stream_shapes_are_violations_never_exceptions(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    for name, line, where, model in STREAM_HOSTILE:
        head = [] if line.get("subtype") == "init" else [INIT_OK]
        s = gz(tmp_path / "t.stream.jsonl.gz", *head, asst("claude-opus-5-5"), line)
        r = verify_pin([t], [s], config.load_pins(), unsafe=[])
        got = [(v["where"], v["model"]) for v in r.violations]
        if where is None:
            assert r.ok and got == [], name
        else:
            assert not r.ok and got == [(where, model)], name

def test_synthetic_only_transcripts_are_not_evidence(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("<synthetic>"), asst("<synthetic>"))
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.no_evidence and r.assistant_messages == 2 and r.synthetic == 2

def test_synthetic_only_streams_are_not_evidence_when_transcripts_are_optional(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("<synthetic>"))
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert not r.ok and r.no_evidence

def test_a_synthetic_init_model_is_a_violation(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {**INIT_OK, "model": "<synthetic>"})
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and r.violations == [{"file": str(s), "line": 1, "where": "init", "model": "<synthetic>"}]


# --- fix round 1: unsafe entries reach verify_pin; size cap -------------------------------------------------

def test_verify_pin_requires_the_unsafe_entries(tmp_path):
    import pytest
    with pytest.raises(TypeError):
        verify_pin([], [], config.load_pins())            # forgetting collect's skipped list is a bug, not a pass

def test_any_skipped_entry_makes_the_pin_unverifiable(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("claude-opus-5-5"))
    r = verify_pin([f], [], config.load_pins(), unsafe=[{"path": "p/evil.jsonl", "reason": "symlink"}])
    assert not r.ok and r.violations == [{"file": "p/evil.jsonl", "line": None, "where": "transcript_unverifiable", "model": "symlink"}]

def test_hard_link_evasion_of_a_subagent_transcript_fails_the_pin(tmp_path):
    # The arm hard-links its off-model subagent transcript so the walk skips it; that must not read as a pass.
    cfg = tmp_path / ".claude"
    before = snapshot(cfg)
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    sub = cfg / "projects/p/s1/subagents/agent-1.jsonl"; w(sub, asst("claude-haiku-4-5"))
    os.link(sub, sub.with_name("agent-1.bak"))
    unsafe: list[dict] = []
    files = collect(cfg, before, tmp_path / "out", skipped=unsafe)
    assert [p.name for p in files] == ["s1.jsonl.gz"]
    r = verify_pin(files, [], config.load_pins(), unsafe=unsafe)
    assert not r.ok
    assert r.violations == [{"file": "p/s1/subagents/agent-1.jsonl", "line": None,
                             "where": "transcript_unverifiable", "model": "hardlinked"}]

def test_an_oversize_transcript_is_skipped_recorded_and_fails_the_pin(tmp_path):
    cfg = tmp_path / ".claude"
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    big = cfg / "projects/p/big.jsonl"
    with open(big, "wb") as fh:
        fh.truncate(MAX_FILE_BYTES + 1)                   # sparse: no real disk use
    skipped: list[dict] = []
    files = collect(cfg, {}, tmp_path / "out", skipped=skipped)
    assert [p.name for p in files] == ["s1.jsonl.gz"]
    assert skipped == [{"path": "p/big.jsonl", "reason": "oversize"}]
    assert "p/big.jsonl" not in snapshot(cfg)
    r = verify_pin(files, [], config.load_pins(), unsafe=skipped)
    assert not r.ok and r.violations[0]["model"] == "oversize"

def test_a_file_that_grows_past_the_cap_while_being_read_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(transcripts, "MAX_FILE_BYTES", 100)
    cfg = tmp_path / ".claude"
    w(cfg / "projects/p/s1.jsonl", asst("claude-opus-5-5"))
    real_walk = transcripts.safe_files
    def walk_then_grow(root, pattern="*.jsonl", *, skipped=None):
        out = real_walk(root, pattern, skipped=skipped)
        with open(cfg / "projects/p/s1.jsonl", "a") as fh:
            fh.write("x" * 500)
        return out
    monkeypatch.setattr(transcripts, "safe_files", walk_then_grow)
    skipped: list[dict] = []
    assert collect(cfg, {}, tmp_path / "out", skipped=skipped) == []
    assert skipped == [{"path": "p/s1.jsonl", "reason": "oversize"}]
    assert not (tmp_path / "out" / "p" / "s1.jsonl.gz").exists()

def test_hashing_and_copying_stream_in_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(transcripts, "CHUNK_BYTES", 7)
    cfg = tmp_path / ".claude"
    w(cfg / "projects/p/s1.jsonl", *[asst("claude-opus-5-5")] * 20)
    import hashlib
    data = (cfg / "projects/p/s1.jsonl").read_bytes()
    assert snapshot(cfg) == {"p/s1.jsonl": hashlib.sha256(data).hexdigest()}
    [out] = collect(cfg, {}, tmp_path / "out")
    assert gzip.open(out, "rb").read() == data

def test_read_safe_on_a_fifo_returns_without_blocking(tmp_path):
    root = tmp_path / "projects"; root.mkdir()
    os.mkfifo(root / "pipe.jsonl")
    got = []
    th = threading.Thread(target=lambda: got.append(transcripts._open_safe(root / "pipe.jsonl", str(root.resolve()))),
                          daemon=True)
    th.start(); th.join(5)
    assert not th.is_alive(), "opening a FIFO blocked"
    assert got == ["not-regular"]

def test_an_entry_swapped_for_a_symlink_after_the_walk_is_changed_under_read(tmp_path, monkeypatch):
    secret = tmp_path / "host-secret.jsonl"; secret.write_text('{"secret": "HOST-PRIVATE"}\n')
    cfg = tmp_path / ".claude"
    victim = cfg / "projects/p/s1.jsonl"; w(victim, asst("claude-opus-5-5"))
    real_walk = transcripts.safe_files
    def walk_then_swap(root, pattern="*.jsonl", *, skipped=None):
        out = real_walk(root, pattern, skipped=skipped)
        victim.unlink(); os.symlink(secret, victim)
        return out
    monkeypatch.setattr(transcripts, "safe_files", walk_then_swap)
    skipped: list[dict] = []
    assert collect(cfg, {}, tmp_path / "out", skipped=skipped) == []
    assert skipped == [{"path": "p/s1.jsonl", "reason": "changed-under-read"}]


# --- a stream without init (controller ruling on concern 2) -----------------------------------------------

def test_assistant_activity_without_init_is_an_unverifiable_version_violation(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", asst("claude-opus-5-5"))
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok
    assert r.violations == [{"file": str(s), "line": None, "where": "claude_code_version", "model": "unverifiable"}]
    assert r.claude_code_versions == ["unverified"] and r.unverified_streams == [str(s)]

def test_model_usage_without_init_is_assistant_activity_too(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {"type": "result", "modelUsage": {"claude-opus-5-5": {}}})
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and [v["model"] for v in r.violations] == ["unverifiable"]

def test_a_stream_with_no_init_and_no_activity_is_recorded_unverified_not_faulted(tmp_path):
    # e.g. a turn that timed out before Claude Code started: the turn's own outcome carries the failure.
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    ok = gz(tmp_path / "a.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    empty = gz(tmp_path / "b.stream.jsonl.gz")
    r = verify_pin([t], [ok, empty], config.load_pins(), unsafe=[])
    assert r.violations == [] and r.ok
    assert r.claude_code_versions == ["2.1.281", "unverified"]      # never reported as the pinned version
    assert r.unverified_streams == [str(empty)]


# --- "checked nothing" is a failure, never a vacuous pass (controller ruling) ----------------------------

def test_nothing_at_all_is_not_evidence(tmp_path):
    r = verify_pin([], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.assistant_messages == 0

def test_nothing_at_all_is_not_evidence_even_when_transcripts_are_not_required(tmp_path):
    r = verify_pin([], [], config.load_pins(), unsafe=[], require_transcripts=False)
    assert not r.ok and r.no_evidence

def test_transcripts_with_no_assistant_message_are_not_evidence(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, {"type": "user", "message": {"content": "hi"}}, {"type": "summary"})
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([f], [s], config.load_pins(), unsafe=[])
    assert not r.ok and r.no_evidence and r.assistant_messages == 0 and r.violations == []

def test_a_transcript_of_only_truncated_lines_is_not_evidence(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text('{"type": "assi')
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.no_evidence and r.truncated_lines == 1

def test_streams_without_any_assistant_event_are_not_evidence_when_transcripts_are_optional(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK)
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert not r.ok and r.no_evidence

def test_streams_alone_pass_when_transcripts_are_optional(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert r.ok and not r.no_evidence and r.stream_assistant_messages == 1 and r.claude_code_versions == ["2.1.281"]

def test_report_serialises_every_field_for_model_pin_json(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("claude-opus-5-5"))
    r = json.loads(verify_pin([f], [], config.load_pins(), unsafe=[]).to_json())
    assert set(r) == {"ok", "assistant_messages", "stream_assistant_messages", "synthetic", "truncated_lines",
                      "claude_code_versions", "no_evidence", "violations", "unverified_streams"}
    assert r["ok"] is True and r["assistant_messages"] == 1


# --- end to end against the fake claude's real output shape (no model calls, no docker) ------------------

def _fake_turn(cfg: Path, cwd: Path, prompt: str, stream: Path) -> None:
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg)}
    env.pop("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR", None)
    env.pop("FAKE_SUBAGENT_MODEL", None)
    out = subprocess.run([sys.executable, str(FAKE_CLAUDE), "-p", prompt, "--model", "claude-opus-5-5",
                          "--output-format", "stream-json"], cwd=cwd, env=env, capture_output=True, text=True,
                         check=True, timeout=60)
    with gzip.open(stream, "wt") as fh:
        fh.write(out.stdout)

def test_fake_claude_turn_collects_and_verifies(tmp_path):
    cfg, cwd = tmp_path / ".claude", tmp_path / "work"; cwd.mkdir()
    before = snapshot(cfg)
    stream = tmp_path / "01.stream.jsonl.gz"
    _fake_turn(cfg, cwd, "FAKE:reply=hi", stream)
    unsafe: list[dict] = []
    files = collect(cfg, before, tmp_path / "out", skipped=unsafe)
    r = verify_pin(files, [stream], config.load_pins(), unsafe=unsafe)
    assert r.ok and r.assistant_messages == 1 and r.stream_assistant_messages == 1, r
    assert r.claude_code_versions == ["2.1.281"]

def test_fake_claude_subagent_on_another_model_is_caught_from_the_collected_transcript(tmp_path):
    cfg, cwd = tmp_path / ".claude", tmp_path / "work"; cwd.mkdir()
    before = snapshot(cfg)
    stream = tmp_path / "01.stream.jsonl.gz"
    _fake_turn(cfg, cwd, "FAKE:subagent_model=claude-haiku-4-5", stream)
    unsafe: list[dict] = []
    files = collect(cfg, before, tmp_path / "out", skipped=unsafe)
    assert len(files) == 2 and "agent-1.jsonl.gz" in {p.name for p in files}
    r = verify_pin(files, [stream], config.load_pins(), unsafe=unsafe)
    assert not r.ok
    assert [(Path(v["file"]).name, v["where"], v["model"]) for v in r.violations] == \
        [("agent-1.jsonl.gz", "assistant", "claude-haiku-4-5")]


def test_a_directory_the_walk_cannot_list_is_recorded_not_silently_dropped(tmp_path):
    # os.walk swallows listing errors by default; a chmod-000 subagents dir would hide an off-model transcript.
    root = tmp_path / ".claude" / "projects"
    w(root / "p/s1.jsonl", asst("claude-opus-5-5"))
    hidden = root / "p/s1/subagents"; w(hidden / "agent-1.jsonl", asst("claude-haiku-4-5"))
    hidden.chmod(0)
    try:
        skipped: list[dict] = []
        assert safe_files(root, skipped=skipped) == [root / "p/s1.jsonl"]
        assert skipped == [{"path": "p/s1/subagents", "reason": "unreadable"}]
    finally:
        hidden.chmod(0o755)


# --- fix round 2: an off-pin message hidden in a "truncated" last line (reviewer probes 1-4) ---------------

OFF = json.dumps(asst("claude-haiku-4-5"))
ON = json.dumps(asst("claude-opus-5-5"))

def _stream_with_tail(path, tail, *, result=None):
    with gzip.open(path, "wt") as fh:
        body = [json.dumps(INIT_OK), ON] + ([json.dumps(result)] if result else [])
        fh.write("\n".join(body) + "\n" + tail)
    return path

def test_probe1_off_pin_object_plus_garbage_as_the_last_transcript_line_fails(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text(ON + "\n" + OFF + "TRAILING_GARBAGE_NO_NEWLINE")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.truncated_lines == 0
    assert [(v["line"], v["where"], v["model"]) for v in r.violations] == \
        [(2, "assistant", "claude-haiku-4-5"), (2, "trailing_garbage", "<uninspected>")]

def test_probe2_off_pin_event_plus_garbage_as_the_last_stream_line_fails(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = _stream_with_tail(tmp_path / "t.stream.jsonl.gz", OFF + "GARBAGE_TAIL")
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and ("stream.assistant", "claude-haiku-4-5") in [(v["where"], v["model"]) for v in r.violations]

def test_probe3_sanity_shapes_still_fail(tmp_path):
    two = tmp_path / "a.jsonl"; two.write_text(ON + OFF + "\n" + ON + "\n")
    crlf = tmp_path / "b.jsonl"; crlf.write_bytes((ON + "\r\n" + OFF + "\r\n").encode())
    bom = tmp_path / "c.jsonl"; bom.write_bytes(b"\xef\xbb\xbf" + (ON + "\n" + OFF + "\n").encode())
    for f in (two, crlf, bom):
        r = verify_pin([f], [], config.load_pins(), unsafe=[])
        assert not r.ok, f.name

def test_probe4_a_whole_subagent_file_that_is_one_corrupted_line_fails(tmp_path):
    main = tmp_path / "main.jsonl"; main.write_text(ON + "\n")
    sub = tmp_path / "agent-1.jsonl"; sub.write_text(OFF + "TAIL_GARBAGE_NO_NEWLINE")
    r = verify_pin([main, sub], [], config.load_pins(), unsafe=[])
    assert not r.ok and ("assistant", "claude-haiku-4-5") in [(v["where"], v["model"]) for v in r.violations]

def test_a_bad_last_line_ending_in_a_newline_is_not_truncation(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text(ON + "\n" + '{"type": "assi' + "\n")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.truncated_lines == 0 and [v["where"] for v in r.violations] == ["unreadable_line"]

def test_an_off_pin_model_visible_in_a_cut_off_last_line_is_a_violation(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text(ON + "\n" + OFF[:-12])       # cut mid-object, model literal complete
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and [(v["where"], v["model"]) for v in r.violations] == [("unreadable_line.model", "claude-haiku-4-5")]

def test_an_escaped_model_key_in_a_bad_line_is_still_found(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(ON + "\n" + '{"type": "assistant", "message": {"mod\\u0065l": "claude-haiku-4-5", "content": [')
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert not r.ok and ("unreadable_line.model", "claude-haiku-4-5") in [(v["where"], v["model"]) for v in r.violations]

def test_a_bad_middle_line_is_scanned_for_models_too(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text(ON + "\n" + OFF[:-12] + "\n" + ON + "\n")
    r = verify_pin([f], [], config.load_pins(), unsafe=[])
    assert [(v["where"], v["model"]) for v in r.violations] == \
        [("unreadable_line", "<uninspected>"), ("unreadable_line.model", "claude-haiku-4-5")]

def test_genuine_truncated_last_lines_still_pass(tmp_path):
    for cut in (ON[:-12], ON[:25], '{"type": "assistant", "message": {"model": "claude-op'):
        f = tmp_path / "s.jsonl"; f.write_text(ON + "\n" + cut)
        r = verify_pin([f], [], config.load_pins(), unsafe=[])
        assert r.ok and r.truncated_lines == 1, cut
        s = _stream_with_tail(tmp_path / "t.stream.jsonl.gz", cut)
        r = verify_pin([f], [s], config.load_pins(), unsafe=[])
        assert r.ok and r.truncated_lines == 2, cut

def test_a_transcript_with_no_decodable_line_is_unverifiable(tmp_path):
    main = tmp_path / "main.jsonl"; main.write_text(ON + "\n")
    sub = tmp_path / "agent-1.jsonl"; sub.write_text('{"type": "assi')
    r = verify_pin([main, sub], [], config.load_pins(), unsafe=[])
    assert not r.ok and r.violations == [{"file": str(sub), "line": None, "where": "transcript_unverifiable",
                                          "model": "no-decodable-lines"}]

# (a) the runner-captured stream is the backstop: every result must carry a well-formed, on-pin modelUsage

def _result(mu=..., **kw):
    r = {"type": "result", "subtype": "success", "is_error": False, **kw}
    if mu is not ...:
        r["modelUsage"] = mu
    return r

def test_a_result_with_an_off_pin_subagent_model_in_model_usage_is_a_violation(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"),
           _result({"claude-opus-5-5": {"inputTokens": 1}, "claude-haiku-4-5": {"inputTokens": 1}}))
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and [(v["where"], v["model"]) for v in r.violations] == [("result.modelUsage", "claude-haiku-4-5")]

def test_a_result_must_carry_a_non_empty_model_usage_with_an_accepted_model(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    for mu, tag in ((..., "<missing>"), ({}, "<empty>"), ({"<synthetic>": {}}, "<no-accepted-model>")):
        s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"), _result(mu))
        r = verify_pin([t], [s], config.load_pins(), unsafe=[])
        assert not r.ok and [(v["where"], v["model"]) for v in r.violations] == [("result.modelUsage", tag)], tag

def test_a_result_with_synthetic_and_accepted_usage_passes(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"),
           _result({"claude-opus-5-5": {}, "<synthetic>": {}}))
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert r.ok and r.synthetic == 1

def test_a_cut_off_result_line_in_a_stream_is_a_violation(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = _stream_with_tail(tmp_path / "t.stream.jsonl.gz", json.dumps(_result({"claude-opus-5-5": {}}))[:30])
    r = verify_pin([t], [s], config.load_pins(), unsafe=[])
    assert not r.ok and [v["where"] for v in r.violations] == ["unreadable_result"]

def test_the_stream_backstop_catches_a_hidden_subagent_even_if_its_transcript_evades(tmp_path):
    # Residual-risk scenario (module docstring): the transcript tree shows nothing off-pin, the stream does.
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"),
           _result({"claude-opus-5-5": {}, "claude-haiku-4-5": {}}))
    assert not verify_pin([t], [s], config.load_pins(), unsafe=[]).ok


# --- ruling: modelUsage is required only when the turn did work ------------------------------------------

NOT_LOGGED_IN = {"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in · Please run /login",
                 "total_cost_usd": 0, "num_turns": 1, "duration_api_ms": 0}

def test_a_no_work_auth_result_without_model_usage_is_not_a_pin_violation(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, NOT_LOGGED_IN)
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert r.violations == []          # (not ok: no evidence — the turn's own outcome carries the failure)

def test_a_no_work_result_with_synthetic_or_empty_usage_is_not_a_violation(tmp_path):
    for mu in ({}, {"<synthetic>": {}}):
        s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("<synthetic>"), _result(mu, total_cost_usd=0))
        r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
        assert r.violations == [], mu

def test_work_done_without_model_usage_is_a_violation(tmp_path):
    tool = {"type": "assistant", "message": {"model": "<synthetic>", "content": [{"type": "tool_use", "name": "Bash"}]}}
    cases = {"real assistant message": [asst("claude-opus-5-5"), _result()],
             "tool_use": [tool, _result()],
             "cost": [_result(total_cost_usd=0.01)],
             "hostile cost": [_result(total_cost_usd="0.01")]}
    for name, events in cases.items():
        s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, *events)
        r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
        assert ("result.modelUsage", "<missing>") in [(v["where"], v["model"]) for v in r.violations], name

def test_present_model_usage_with_an_off_pin_key_is_a_violation_even_without_work(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, _result({"claude-haiku-4-5": {}}, total_cost_usd=0))
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert [(v["where"], v["model"]) for v in r.violations] == [("result.modelUsage", "claude-haiku-4-5")]

def test_malformed_model_usage_is_a_violation_even_without_work(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, _result(["claude-opus-5-5"], total_cost_usd=0))
    r = verify_pin([], [s], config.load_pins(), unsafe=[], require_transcripts=False)
    assert [(v["where"], v["model"]) for v in r.violations] == [("result.modelUsage", "<malformed:list>")]
