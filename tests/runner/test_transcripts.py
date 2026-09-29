import gzip, json, os, subprocess, sys
from pathlib import Path

from runner import config
from runner.transcripts import snapshot, collect, verify_pin, safe_files

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

def test_a_fifo_is_skipped_without_blocking(tmp_path):
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
    r = verify_pin([f], [], config.load_pins())
    assert not r.ok and r.violations == [{"file": str(f), "line": 2, "where": "assistant", "model": "claude-haiku-4-5"}]

def test_synthetic_messages_are_counted_not_faulted(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("<synthetic>"), asst("claude-opus-5-5"))
    r = verify_pin([f], [], config.load_pins())
    assert r.ok and r.synthetic == 1 and r.assistant_messages == 2

def test_stream_assistant_events_and_model_usage_are_checked(tmp_path):     # review C-6
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-sonnet-5"),
           {"type": "result", "modelUsage": {"claude-opus-5-5": {}, "claude-haiku-4-5": {}}})
    r = verify_pin([t], [s], config.load_pins())
    assert [v["where"] for v in r.violations] == ["stream.assistant", "result.modelUsage"]

def test_the_init_model_is_checked(tmp_path):
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {**INIT_OK, "model": "claude-sonnet-5"})
    r = verify_pin([t], [s], config.load_pins())
    assert not r.ok and r.violations == [{"file": str(s), "line": 1, "where": "init", "model": "claude-sonnet-5"}]

def test_streams_alone_are_not_evidence_for_an_arm_step(tmp_path):         # review C-6
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([], [s], config.load_pins())
    assert not r.ok and r.no_evidence

def test_a_wrong_claude_code_version_is_a_violation(tmp_path):             # review C-16
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", {**INIT_OK, "claude_code_version": "2.1.290"})
    r = verify_pin([t], [s], config.load_pins())
    assert r.violations == [{"file": str(s), "line": 1, "where": "claude_code_version", "model": "2.1.290"}]

def test_a_truncated_last_line_is_counted_not_fatal(tmp_path):             # review C-6
    f = tmp_path / "s.jsonl"; f.write_text(json.dumps(asst("claude-opus-5-5")) + "\n" + '{"type": "assi')
    r = verify_pin([f], [], config.load_pins())
    assert r.ok and r.truncated_lines == 1

def test_an_oversize_stream_line_is_counted_as_uninspected(tmp_path):
    # session.py writes {"type": "bk_oversize_line"} in place of a stream line over its reader limit.
    t = tmp_path / "s.jsonl"; w(t, asst("claude-opus-5-5"))
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, {"type": "bk_oversize_line", "bytes": 99})
    r = verify_pin([t], [s], config.load_pins())
    assert r.ok and r.truncated_lines == 1


# --- "checked nothing" is a failure, never a vacuous pass (controller ruling) ----------------------------

def test_nothing_at_all_is_not_evidence(tmp_path):
    r = verify_pin([], [], config.load_pins())
    assert not r.ok and r.assistant_messages == 0

def test_nothing_at_all_is_not_evidence_even_when_transcripts_are_not_required(tmp_path):
    r = verify_pin([], [], config.load_pins(), require_transcripts=False)
    assert not r.ok and r.no_evidence

def test_transcripts_with_no_assistant_message_are_not_evidence(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, {"type": "user", "message": {"content": "hi"}}, {"type": "summary"})
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([f], [s], config.load_pins())
    assert not r.ok and r.no_evidence and r.assistant_messages == 0 and r.violations == []

def test_a_transcript_of_only_truncated_lines_is_not_evidence(tmp_path):
    f = tmp_path / "s.jsonl"; f.write_text('{"type": "assi')
    r = verify_pin([f], [], config.load_pins())
    assert not r.ok and r.no_evidence and r.truncated_lines == 1

def test_streams_without_any_assistant_event_are_not_evidence_when_transcripts_are_optional(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK)
    r = verify_pin([], [s], config.load_pins(), require_transcripts=False)
    assert not r.ok and r.no_evidence

def test_streams_alone_pass_when_transcripts_are_optional(tmp_path):
    s = gz(tmp_path / "t.stream.jsonl.gz", INIT_OK, asst("claude-opus-5-5"))
    r = verify_pin([], [s], config.load_pins(), require_transcripts=False)
    assert r.ok and not r.no_evidence and r.stream_assistant_messages == 1 and r.claude_code_versions == ["2.1.281"]

def test_report_serialises_every_field_for_model_pin_json(tmp_path):
    f = tmp_path / "s.jsonl"; w(f, asst("claude-opus-5-5"))
    r = json.loads(verify_pin([f], [], config.load_pins()).to_json())
    assert set(r) == {"ok", "assistant_messages", "stream_assistant_messages", "synthetic", "truncated_lines",
                      "claude_code_versions", "no_evidence", "violations"}
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
    files = collect(cfg, before, tmp_path / "out")
    r = verify_pin(files, [stream], config.load_pins())
    assert r.ok and r.assistant_messages == 1 and r.stream_assistant_messages == 1, r
    assert r.claude_code_versions == ["2.1.281"]

def test_fake_claude_subagent_on_another_model_is_caught_from_the_collected_transcript(tmp_path):
    cfg, cwd = tmp_path / ".claude", tmp_path / "work"; cwd.mkdir()
    before = snapshot(cfg)
    stream = tmp_path / "01.stream.jsonl.gz"
    _fake_turn(cfg, cwd, "FAKE:subagent_model=claude-haiku-4-5", stream)
    files = collect(cfg, before, tmp_path / "out")
    assert len(files) == 2 and "agent-1.jsonl.gz" in {p.name for p in files}
    r = verify_pin(files, [stream], config.load_pins())
    assert not r.ok
    assert [(Path(v["file"]).name, v["where"], v["model"]) for v in r.violations] == \
        [("agent-1.jsonl.gz", "assistant", "claude-haiku-4-5")]
