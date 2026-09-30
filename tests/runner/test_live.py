"""The live per-turn feed and `runner watch` (runner.live), offline: no Docker, no model, tmp state only.

Event shapes: `stream-probe-p1.jsonl` is a real Claude Code 2.1.281 stream (probe P1). No committed real stream
contains a tool call, so the tool_use/tool_result blocks below are the real ones from probe P3's committed
transcript (`results/probe/P3/…/44cba6d9-….jsonl.gz`: an `Agent` call and its hand-back), placed in P1's real
`assistant` envelope; the transcript's `message` is the same Anthropic message object the stream carries. The
Bash/Edit inputs are NOT from a captured stream (none has one): they are Claude Code's documented tool inputs, and
the tests using them say so."""
import copy
import io
import json
import sys
from pathlib import Path

import pytest

from runner import credentials, docker, live, secrets, session
from runner.paths import Paths

FIXTURE = Path(__file__).parent / "fixtures" / "stream-probe-p1.jsonl"
P1 = [json.loads(ln) for ln in FIXTURE.read_text().splitlines() if ln.strip()]
INIT, ASSISTANT, RATE, RESULT = P1

# probe P3's real blocks (see the module docstring)
AGENT_USE = {"type": "tool_use", "id": "toolu_015mBFpUg6Qcdd1V9B6byApr", "name": "Agent",
             "input": {"description": "Reply sub-ok", "prompt": "Reply with exactly: sub-ok", "model": "haiku",
                       "run_in_background": False}, "caller": {"type": "direct"}}
AGENT_RESULT = {"tool_use_id": "toolu_015mBFpUg6Qcdd1V9B6byApr", "type": "tool_result",
                "content": [{"type": "text", "text": "[Subagent hand-back] sub-ok"}]}


def assistant_with(*blocks):
    ev = copy.deepcopy(ASSISTANT)
    ev["message"]["content"] = list(blocks)
    return ev


def user_with(*blocks):
    return {"type": "user", "message": {"role": "user", "content": list(blocks)}, "parent_tool_use_id": None,
            "session_id": INIT["session_id"]}


def fmt(ev, st=None):
    return live.format_event(ev, st or live.FeedState())


# ---- pure formatting -----------------------------------------------------------------------------------------

def test_the_real_p1_stream_formats_to_init_text_and_result_and_drops_the_allowed_rate_limit_tick():
    st = live.FeedState()
    lines = [b for ev in P1 for b in live.format_event(ev, st)]
    assert lines[0] == f"init: model {INIT['model']}, session {INIT['session_id'][:8]}"
    assert lines[1] == "text: ok"
    assert len(lines) == 3                                          # the rate_limit_event (status allowed) is dropped
    assert lines[2].startswith("result: ok (success), cost $0.0377, 1 model turns")
    assert lines[2].endswith("— ok")


def test_a_real_agent_call_shows_subagent_start_and_its_tool_result_shows_subagent_done():
    st = live.FeedState()
    assert fmt(assistant_with(AGENT_USE), st) == ["subagent start: Reply sub-ok (haiku)"]
    assert fmt(user_with(AGENT_RESULT), st) == ["subagent done: Reply sub-ok"]
    assert st.subagents == {}


def test_events_inside_a_subagent_are_marked_sub():
    ev = assistant_with({"type": "text", "text": "sub-ok"})
    ev["parent_tool_use_id"] = AGENT_USE["id"]
    assert fmt(ev) == ["[sub] text: sub-ok"]


def test_tool_summaries_for_documented_bash_edit_and_grep_inputs():
    # Documented Claude Code tool inputs, not captured ones (module docstring).
    assert live.tool_summary("Bash", {"command": "uv run pytest -q", "description": "run tests"}) == \
        "Bash: uv run pytest -q"
    assert live.tool_summary("Edit", {"file_path": "src/x.py", "old_string": "a", "new_string": "b"}) == \
        "Edit: src/x.py"
    assert live.tool_summary("Grep", {"pattern": "def main", "path": "src"}) == "Grep: def main  in src"
    assert live.tool_summary("Unknown", {"n": 3}) == "Unknown: (n)"


def test_a_failed_non_agent_tool_result_is_shown_as_a_tool_error():
    res = {"tool_use_id": "toolu_x", "type": "tool_result", "is_error": True, "content": "exit 1\nboom"}
    assert fmt(user_with(res)) == ["tool error: exit 1 boom"]


def test_feed_lines_are_single_lines_trimmed_to_160_for_tools_and_200_for_text(tmp_state):
    f = _feed(Paths("t", "dryrun"), step=1)
    assert f.start()
    f.event(json.dumps(assistant_with({"type": "tool_use", "id": "t1", "name": "Bash",
                                       "input": {"command": "echo " + "x" * 400 + "\nsecond line"}})))
    f.event(json.dumps(assistant_with({"type": "text", "text": "y" * 500})))
    f.end("ok")
    body = [ln.split("] ", 1)[1] for ln in f.path.read_text().splitlines()]
    tool, text = body[1], body[2]
    assert tool.startswith("tool Bash: echo xxx") and len(tool) == live.TOOL_MAX and tool.endswith("…")
    assert text.startswith("text: yyy") and len(text) == live.TEXT_MAX
    assert all("\n" not in b for b in body)


# ---- the writer ------------------------------------------------------------------------------------------------

def _feed(p, *, step=1, run="b", stem="arm-a1-001", clock=None, cred=None):
    kw = {"clock": clock} if clock else {}
    return live.Feed(p, step=step, run=run, stem=stem, role="arm", attempt=1, n=1, evidence=p.step(step),
                     redact=secrets.live_redactor(cred or credentials.dummy(), [p.home]), **kw)


def test_a_token_shaped_string_and_the_known_values_are_redacted_before_they_reach_the_live_file(tmp_state):
    p = Paths("t", "dryrun")
    ghp = "ghp_" + "Z" * 36                              # built at run time: no token shape in this source file
    pat = "github_pat_" + "Q" * 50
    ant = "sk-ant-" + "k" * 40
    real = credentials.Credential("r" * 12 + "-oauth-" + "r" * 20)
    f = _feed(p, cred=real)
    assert f.start()
    f.event(json.dumps(assistant_with({"type": "tool_use", "id": "t1", "name": "Bash",
                                       "input": {"command": f"GH_TOKEN={ghp} gh issue list"}})))
    f.event(json.dumps(assistant_with({"type": "text", "text": f"my pat is {pat} and {ant} and "
                                                              f"{real.raw_for_scanner()}"})))
    f.end("ok")
    text = f.path.read_text()
    for secret in (ghp, pat, ant, real.raw_for_scanner()):
        assert secret not in text
    assert text.count(secrets.REDACTED) == 4
    assert secrets.scan_tree(p.live, [real.raw_for_scanner()]) == []
    # the dry-run dummy (what the dry-run report searches state/ for) is redacted too
    f_dummy = _feed(p, stem="arm-a1-002")
    assert f_dummy.start()
    f_dummy.event(json.dumps(assistant_with({"type": "text", "text": f"token {secrets.DRY_RUN_TOKEN}"})))
    f_dummy.end("ok")
    assert secrets.DRY_RUN_TOKEN not in f_dummy.path.read_text()
    assert secrets.scan_tree(p.live, [secrets.DRY_RUN_TOKEN]) == []


def test_the_arm_homes_pat_value_is_redacted(tmp_state):
    p = Paths("t", "dryrun")
    value = "ghs_" + "W" * 36
    (p.home / ".config/gh").mkdir(parents=True)
    (p.home / ".config/gh/hosts.yml").write_text(f"github.com:\n    oauth_token: {value}\n")
    f = _feed(p)
    assert f.start()
    f.event(json.dumps(assistant_with({"type": "text", "text": f"cat hosts.yml -> {value}"})))
    f.end("ok")
    assert value not in f.path.read_text()


def test_scan_step_and_scan_arm_cover_the_live_feeds(tmp_state, monkeypatch):
    """A token the write-time redaction did not know is still found: scan_step scans the feeds like the stream."""
    p = Paths("t", "dryrun")
    p.live.mkdir(parents=True)
    (p.live / "03-b-arm-a1-001-20261001T000000Z.log").write_text("leak " + "ghp_" + "Y" * 36 + "\n")
    (p.live / "04-b-arm-a1-001-20261001T000000Z.log").write_text("clean\n")
    assert [Path(f.path).name for f in secrets.scan_step(p, 3)] == ["03-b-arm-a1-001-20261001T000000Z.log"]
    assert secrets.scan_step(p, 4) == []
    monkeypatch.setattr(secrets, "keychain_pat", lambda pass_, arm: None)
    assert len(secrets.scan_arm(p, [], snapshots=False)) == 1


def test_a_faked_turn_writes_and_flushes_each_live_line_while_the_turn_is_still_running(tmp_state, tmp_path,
                                                                                         monkeypatch):
    """The stand-in for the docker CLI prints P1's init and assistant events, then waits until the live feed
    already holds the assistant text (so it was flushed mid-turn), and only then prints the result."""
    p = Paths("t", "dryrun")
    live_dir = p.live
    child = [sys.executable, "-c", f"""
import glob, json, sys, time
for ev in {json.dumps(INIT)!r}, {json.dumps(ASSISTANT)!r}:
    print(ev, flush=True)
seen = False
for _ in range(200):
    for f in glob.glob({str(live_dir / '01-*.log')!r}):
        if 'text: ok' in open(f).read():
            seen = True
    if seen:
        break
    time.sleep(0.05)
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                  "result": "seen-mid-turn" if seen else "NOT-SEEN", "total_cost_usd": 0.5}}), flush=True)
"""]
    monkeypatch.setattr(docker, "run_argv", lambda spec: child)
    monkeypatch.setattr(docker, "stop", lambda name: None)
    monkeypatch.setattr(docker, "exit_state", lambda name: (False, 0))
    monkeypatch.setattr(docker, "remove", lambda name: None)
    t = session.Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", tmp_path / "inbox", "arm",
                     True, None)
    r = session.run_turn(t, credentials.dummy(), p.step(1), 30)
    assert r.outcome == "ok" and r.final_text == "seen-mid-turn"
    (feed,) = list(live_dir.glob("01-b-arm-a1-001-*.log"))
    lines = feed.read_text().splitlines()
    assert "turn start: t/dryrun step 1 run b" in lines[0]
    assert "turn end: ok, cost $0.5000, " in lines[-1]
    assert not (live_dir / live.CURRENT).exists()                  # the pointer is gone once the turn ended


def test_run_label_reads_the_evidence_dir(tmp_state):
    p = Paths("t", "dryrun")
    assert live.run_label(p, p.step(3) / "a") == "a"
    assert live.run_label(p, p.step(3)) == "b"
    assert live.run_label(p, p.setup_results) == "setup"
    assert live.run_label(p, tmp_state / "elsewhere") == "-"


# ---- watch ------------------------------------------------------------------------------------------------------

def _tree(root):
    return {str(x): (x.stat().st_mtime_ns, x.stat().st_size) for x in sorted(root.rglob("*"))}


def test_watch_waits_with_no_running_turn_then_follows_a_turn_and_switches_to_the_next(tmp_state):
    p = Paths("t", "dryrun")
    out = io.StringIO()
    feeds: list = []
    script = [
        lambda: None,                                                           # nothing running yet
        lambda: (feeds.append(_feed(p, stem="arm-a1-001")), feeds[0].start(),
                 feeds[0].event(json.dumps(INIT))),
        lambda: feeds[0].event(json.dumps(ASSISTANT)),
        lambda: (feeds[0].end("ok"), feeds.append(_feed(p, stem="arm-a1-002")), feeds[1].start(),
                 feeds[1].event(json.dumps(assistant_with(AGENT_USE)))),
        lambda: feeds[1].event(json.dumps(RESULT)),
    ]
    steps = iter(script)
    done = []

    def sleep(_):
        try:
            next(steps)()
        except StopIteration:
            done.append(True)
    live.follow(out, "t", "dryrun", sleep=sleep, until=lambda: bool(done))
    text = out.getvalue()
    assert "no running turn; waiting" in text
    i1 = text.index("=== t/dryrun  step 1  run b  arm attempt 1 turn 1")
    assert text.index("[01b arm-a1-001] init:") > i1
    assert text.index("[01b arm-a1-001] text: ok") > i1
    assert text.index("[01b arm-a1-001] turn end: ok") < text.index("--- turn ended ---")
    i2 = text.index("=== t/dryrun", i1 + 1)
    assert text.index("[01b arm-a1-002] subagent start: Reply sub-ok") > i2
    assert text.index("[01b arm-a1-002] result: ok") > i2


def test_watch_ignores_a_pointer_left_by_a_dead_runner(tmp_state):
    p = Paths("t", "dryrun")
    f = _feed(p)
    assert f.start()                                              # never ended: a SIGKILLed runner's leftovers
    assert live.find_current("t", "dryrun", alive=lambda pid: False) is None
    assert live.find_current("t", "dryrun").path == f.path        # this process is alive
    assert live.find_current("t", "other") is None and live.find_current("u") is None


def test_watch_writes_nothing(tmp_state):
    p = Paths("t", "dryrun")
    f = _feed(p)
    assert f.start()
    f.event(json.dumps(INIT))
    before = _tree(tmp_state)
    ticks = iter(range(3))
    live.follow(io.StringIO(), sleep=lambda _: None, until=lambda: next(ticks, None) is None)
    assert _tree(tmp_state) == before


def test_the_cli_watch_neither_takes_the_lock_nor_refuses_while_halted(tmp_state, monkeypatch):
    from runner import cli, faults, preflight
    ledger, halted = faults.ledger_paths("pass1")
    halted.parent.mkdir(parents=True, exist_ok=True)
    halted.write_text(json.dumps({"reason": "test"}))
    monkeypatch.setattr(preflight, "lock", lambda *a, **k: pytest.fail("watch took the runner lock"))
    got = {}

    def fake_follow(out, pass_, arm, poll):
        got.update(pass_=pass_, arm=arm)
        raise KeyboardInterrupt
    monkeypatch.setattr(live, "follow", fake_follow)
    assert cli.main(["watch", "--pass", "pass1", "--arm", "control"]) == 0
    assert got == {"pass_": "pass1", "arm": "control"}


# ---- fix round 1 ------------------------------------------------------------------------------------------------

CONTROLS = "\x1b[1A\x1b[2K\x08\x07\x9b\x7f\x00"          # ESC sequences, BS, BEL, C1 CSI, DEL, NUL


def _has_control(text):
    return any(ord(c) < 0x20 and c != "\n" or 0x7f <= ord(c) <= 0x9f for c in text)


def test_control_characters_in_model_text_and_tool_input_reach_the_feed_visibly_escaped(tmp_state):
    p = Paths("t", "dryrun")
    f = _feed(p)
    assert f.start()
    f.event(json.dumps(assistant_with({"type": "text", "text": f"before{CONTROLS}after"})))
    f.event(json.dumps(assistant_with({"type": "tool_use", "id": "t1", "name": "Bash",
                                       "input": {"command": f"echo {CONTROLS}x"}})))
    f.end("ok")
    text = f.path.read_text()
    assert not _has_control(text)
    assert "text: before\\x1b[1A\\x1b[2K\\x08\\x07\\x9b\\x7f\\x00after" in text
    assert "tool Bash: echo \\x1b[1A" in text


def test_watch_escapes_control_characters_from_a_feed_it_did_not_write(tmp_state):
    p = Paths("t", "dryrun")
    f = _feed(p)
    assert f.start()
    with open(f.path, "a") as fh:                                   # an older build's, or a tampered, feed line
        fh.write(f"raw {CONTROLS} line\n")
    out = io.StringIO()
    ticks = iter(range(2))
    live.follow(out, "t", "dryrun", sleep=lambda _: None, until=lambda: next(ticks, None) is None)
    assert "raw \\x1b[1A" in out.getvalue() and not _has_control(out.getvalue())


def test_a_feed_that_disables_itself_says_so_in_the_pointer_and_watch_prints_it(tmp_state):
    p = Paths("t", "dryrun")
    f = _feed(p)
    assert f.start()
    f.event(json.dumps(INIT))
    f._fh.close()                                                   # the next write fails (as on a full disk)
    f.event(json.dumps(ASSISTANT))
    assert json.loads((p.live / live.CURRENT).read_text())["feed"] == "disabled: ValueError"
    out = io.StringIO()
    ticks = iter(range(2))
    live.follow(out, "t", "dryrun", sleep=lambda _: None, until=lambda: next(ticks, None) is None)
    assert "live feed disabled (ValueError)" in out.getvalue()
    assert "the turn itself is still running" in out.getvalue()
