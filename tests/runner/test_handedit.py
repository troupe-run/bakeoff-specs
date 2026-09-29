"""Task 16: the unannounced step-2 hand edit. Offline: pure parts (scope plan, probe text, mentions, facts) and the
`apply` sequence with every container call replaced by a recording fake (Docker-backed checks live in
test_handedit_docker.py)."""
import gzip, json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import handedit, gitops, session
from runner.faults import HarnessFault
from runner.transcripts import PinReport
from tests.runner.conftest import make_test_ctx


# ---- pure parts (the brief's tests, verbatim) ------------------------------------------------------------------

def test_python_changes_are_in_scope_and_side_effects_are_cleaned_not_failed():   # review C-11
    plan = handedit.scope_plan(" M src/troupe/cli.py\n?? tests/test_theatre_env.py\n?? src/troupe/__pycache__/cli.cpython-312.pyc\n"
                               "?? .pytest_cache/v/cache/nodeids\n M uv.lock\n")
    assert plan.py == ["src/troupe/cli.py", "tests/test_theatre_env.py"]
    assert plan.remove == [".pytest_cache/v/cache/nodeids", "src/troupe/__pycache__/cli.cpython-312.pyc"]
    assert plan.restore == ["uv.lock"] and plan.violations == []


def test_a_tracked_non_python_edit_or_a_deletion_is_a_violation():
    assert handedit.scope_plan(" M src/troupe/cli.py\n M docs/spec.md\n").violations == ["docs/spec.md (modified)"]
    assert handedit.scope_plan(" D src/troupe/cli.py\n").violations == ["src/troupe/cli.py (deleted)"]


def test_no_python_change_at_all_is_a_violation():
    assert handedit.scope_plan("").violations == ["no Python file changed"]


def test_probe_checks_env_default_and_explicit_flag_precedence():
    s = handedit.PROBE_SH
    assert "TROUPE_THEATRE=/tmp/t uv run troupe config show a" in s
    assert "TROUPE_THEATRE=/tmp/t uv run troupe config show --theatre /tmp/u a" in s


def test_mentions_count_assistant_text_and_tool_inputs_but_not_tool_results(tmp_path):   # review C-10
    f = tmp_path / "s.jsonl.gz"
    with gzip.open(f, "wt") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "I see TROUPE_THEATRE is supported."},
            {"type": "tool_use", "name": "Grep", "input": {"pattern": "TROUPE_THEATRE"}}]}}) + "\n")
        fh.write(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "cli.py: os.environ.get('TROUPE_THEATRE')"}]}}) + "\n")
    assert handedit.mentions([f], "TROUPE_THEATRE") == 2


def test_detection_facts_are_recorded_not_scored():
    facts = handedit.facts_from(probe_ok=True, non_py_mentions=["docs/spec.md"], session_mentions=2, po_mentions=0,
                                teammate_test_kept=True)
    assert facts == {"feature_kept": True, "documented_in": ["docs/spec.md"], "mentioned_in_session": True,
                     "session_mentions": 2, "raised_with_po": False, "teammate_test_kept": True}


# ---- pure parts (added) ------------------------------------------------------------------------------------------

def test_a_staged_rename_a_conflict_or_a_quoted_path_is_a_violation():
    assert handedit.scope_plan("R  a.py -> b.py\n").violations == ["a.py -> b.py (renamed or copied)"]
    assert handedit.scope_plan("UU src/x.py\n").violations == ["src/x.py (unmerged)"]
    assert handedit.scope_plan(' M "src/we\\tird.py"\n').violations == ['"src/we\\tird.py" (unusual name)']


def test_a_lockfile_in_a_subdirectory_is_restored_but_other_tracked_config_is_not():
    plan = handedit.scope_plan(" M a.py\n M pkg/uv.lock\n M pyproject.toml\n")
    assert plan.restore == ["pkg/uv.lock"] and plan.violations == ["pyproject.toml (modified)"]


def test_the_same_assistant_message_in_the_stream_and_the_transcript_counts_once(tmp_path):
    ev = {"type": "assistant", "message": {"id": "msg_1", "content": [{"type": "text", "text": "TROUPE_THEATRE"}]}}
    stream, transcript = tmp_path / "arm.stream.jsonl.gz", tmp_path / "t.jsonl.gz"
    for f in (stream, transcript):
        with gzip.open(f, "wt") as fh:
            fh.write(json.dumps(ev) + "\n")
    assert handedit.mentions([stream, transcript], "TROUPE_THEATRE") == 1


def test_mentions_skip_malformed_lines_and_odd_shapes_without_raising(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text("TROUPE_THEATRE not json\n"
                 + json.dumps({"type": "assistant", "message": "TROUPE_THEATRE"}) + "\n"
                 + json.dumps({"type": "assistant", "message": {"content": ["TROUPE_THEATRE", 3]}}) + "\n"
                 + json.dumps(["TROUPE_THEATRE"]) + "\n"
                 + json.dumps({"type": "assistant", "message": {"content": [
                     {"type": "text", "text": "TROUPE_THEATRE twice TROUPE_THEATRE"}]}}) + "\n")
    assert handedit.mentions([f], "TROUPE_THEATRE") == 2


def test_the_prompt_is_the_config_file_without_its_path_comment():
    assert handedit.PROMPT.startswith("You are a developer on this project")
    assert "-->" not in handedit.PROMPT and "TROUPE_THEATRE" in handedit.PROMPT


# ---- apply: the sequence, with every container call faked --------------------------------------------------------

def _pin(ok=True, violations=(), no_evidence=False):
    return PinReport(ok=ok, assistant_messages=1, stream_assistant_messages=1, synthetic=0, truncated_lines=0,
                     claude_code_versions=["2.1.281"], no_evidence=no_evidence, violations=list(violations))


def _turn(outcome="ok", stream=None, cost=0.25, credential_files=()):
    return session.TurnResult("sid", outcome, "changed src/cli.py", {}, {}, cost, {}, {}, 1.0, [], stream,
                              credential_files=list(credential_files))


STEP1 = {"tests.hidden.test_a::t1": "passed", "tests.hidden.test_a::t2": "failed"}
GOOD_PROBE = '{"env_default":true,"flag_wins":true,"unchanged_without_env":true}\n'


class World:
    """Records every harness call `apply` makes, in order; each try's behaviour is scripted."""

    def __init__(self, mp, ctx, *, outcomes=("ok",), pins=None, porcelains=(" M src/cli.py\n",), probes=(GOOD_PROBE,),
                 rechecks=(STEP1,), state=None, scoreable=True):
        self.ctx, self.calls = ctx, []
        self.outcomes, self.pins = list(outcomes), list(pins or [_pin()] * len(outcomes))
        self.porcelains, self.probes, self.rechecks = list(porcelains), list(probes), list(rechecks)
        self.turn_specs, self.verify_args, self.scoreable = [], [], scoreable
        st = state or gitops.RepoState("main", False, "h0", "h0", True)
        p = ctx.paths
        p.work.mkdir(parents=True, exist_ok=True); p.home.mkdir(parents=True, exist_ok=True)
        log = self.calls.append

        def run_turn(t, cred, out, timeout):
            self.turn_specs.append(t)
            log(("turn", t.attempt))
            s = out / "turns" / f"{session.stem(t)}.stream.jsonl.gz"; s.parent.mkdir(parents=True, exist_ok=True)
            s.write_bytes(b"")
            return _turn(self.outcomes.pop(0), s)

        class Stage:
            def __init__(self, *a): self.net = "bk-net-test"; log(("stage", a[2]))
            def __enter__(self): return self
            def __exit__(self, *e): log(("stage-exit",))

        def collect(cfg, before, dest, skipped=None):
            log(("collect",)); return [dest / "t.jsonl.gz"]

        def verify_pin(files, streams, pins, *, unsafe, require_transcripts=True, stream_outcomes=None):
            self.verify_args.append((list(files), list(streams), unsafe, dict(stream_outcomes or {})))
            log(("verify",)); return self.pins.pop(0)

        def porcelain(p_): log(("porcelain",)); return self.porcelains.pop(0)

        def commit_all(p_, who, msg): log(("commit", who, msg)); return "sha1"

        def prepare(p_, sha, label, out, **k):
            log(("prepare", sha, label)); return SimpleNamespace(hidden_copy=out / "copy", prep={"hidden": {"ok": True}})

        def run_script(p_, copy, script): log(("probe", script == handedit.PROBE_SH)); return self.probes.pop(0)

        def run(p_, copy, step, out, install_failed=False):
            log(("recheck", step, install_failed))
            return SimpleNamespace(tests=self.rechecks.pop(0), scoreable=self.scoreable,
                                   attribution=None if self.scoreable else "harness-fault: x")

        mp.setattr(handedit.session, "run_turn", run_turn)
        mp.setattr(handedit.egress, "Stage", Stage)
        mp.setattr(handedit.transcripts, "snapshot", lambda cfg: log(("tsnap",)) or {})
        mp.setattr(handedit.transcripts, "collect", collect)
        mp.setattr(handedit.transcripts, "verify_pin", verify_pin)
        mp.setattr(handedit.gitops, "state", lambda p_: log(("state",)) or st)
        mp.setattr(handedit.gitops, "porcelain", porcelain)
        mp.setattr(handedit.gitops, "remove_untracked", lambda p_, x: log(("remove", list(x))))
        mp.setattr(handedit.gitops, "checkout_paths", lambda p_, x: log(("checkout", list(x))))
        mp.setattr(handedit.gitops, "commit_all", commit_all)
        mp.setattr(handedit.gitops, "main_sha", lambda p_: "sha1")
        mp.setattr(handedit.gitops, "log", lambda p_, a, b: [{"sha": "sha1", "author": "Sam Teammate", "subject": handedit.MESSAGE}])
        mp.setattr(handedit.gitops, "numstat", lambda p_, a, b: [(3, 1, "src/cli.py")])
        mp.setattr(handedit.gitops, "show", lambda p_, sha: "diff --git a/src/cli.py b/src/cli.py\n")
        mp.setattr(handedit.hidden, "prepare", prepare)
        mp.setattr(handedit.hidden, "run_script", run_script)
        mp.setattr(handedit.hidden, "run", run)
        mp.setattr(handedit.repo, "recover", lambda p_: log(("recover",)))
        mp.setattr(handedit.repo, "snapshot", lambda p_, s: log(("snapshot", s)))
        mp.setattr(handedit.repo, "restore", lambda p_, s: log(("restore", s)))

    def names(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def ctx(tmp_state, tmp_path):
    c = make_test_ctx(tmp_path, arm="dryrun", step=2)
    c.sleep = lambda s: None
    return c


def test_a_good_edit_is_committed_as_sam_teammate_probed_rechecked_and_becomes_snapshot_2(ctx, monkeypatch):
    w = World(monkeypatch, ctx)
    edit = handedit.apply(ctx, STEP1)
    n = w.names()
    assert n[:3] == ["recover", "state", "snapshot"] and w.calls[2] == ("snapshot", "02-pre-edit")
    assert ("commit", gitops.TEAMMATE, handedit.MESSAGE) in w.calls
    order = [n.index(x) for x in ("turn", "stage-exit", "collect", "verify", "porcelain", "commit", "prepare",
                                  "probe", "recheck")]
    assert order == sorted(order)
    assert w.calls[-1] == ("snapshot", 2) and n.count("snapshot") == 2 and "restore" not in n
    assert ("prepare", "sha1", "02-hand-edit") in w.calls and ("probe", True) in w.calls
    assert ("recheck", 1, False) in w.calls
    assert (edit.sha, edit.files, edit.tries) == ("sha1", ["src/cli.py"], 1)
    assert edit.numstat == [(3, 1, "src/cli.py")] and edit.probe == json.loads(GOOD_PROBE)
    out = ctx.out / "hand-edit"
    rec = json.loads((out / "edit.json").read_text())
    assert (rec["sha"], rec["author"], rec["lines_added"], rec["lines_removed"]) == ("sha1", "Sam Teammate", 3, 1)
    assert json.loads((out / "recheck.json").read_text())["differences"] == {}
    for f in ("diff.patch", "probe.json", "model-pin-t1.json"):
        assert (out / f).exists()


def test_the_teammate_turn_is_isolated_pinned_and_in_its_own_fresh_home_and_inbox(ctx, monkeypatch):
    p = ctx.paths
    stale = p.teammate_home(1) / "leftover.txt"; stale.parent.mkdir(parents=True); stale.write_text("old")
    w = World(monkeypatch, ctx)
    handedit.apply(ctx, STEP1)
    (t,) = w.turn_specs
    assert t.role == "teammate" and t.step == 2 and t.message == handedit.PROMPT
    assert t.env["BK_ISOLATED"] == "1" and t.env["BK_MODEL"] == ctx.pins.model   # -> --setting-sources "", pinned
    assert "BK_RESUME" not in t.env and "BK_PLUGIN_DIRS" not in t.env
    assert t.inbox_dir == p.inbox("teammate") and t.config_dir == p.teammate_home(1) / ".claude"
    homes = [m for m in t.mounts if m.ctr == "/home/actor"]
    assert [m.host for m in homes] == [p.teammate_home(1)] and not stale.exists()
    for arm_mount in (p.home, p.work):         # the arm's own mounts: the teammate's inbox and home are outside both
        assert not p.inbox("teammate").is_relative_to(arm_mount)
        assert not p.teammate_home(1).is_relative_to(arm_mount)
    assert not p.teammate_home(1).exists()     # thrown away once its transcripts were collected


def test_the_pin_check_gets_the_runner_stream_the_unsafe_list_and_the_stream_outcome(ctx, monkeypatch):
    w = World(monkeypatch, ctx)
    handedit.apply(ctx, STEP1)
    ((files, streams, unsafe, outcomes),) = w.verify_args
    assert files and len(streams) == 1 and streams[0].name.startswith("teammate-a1-")
    assert unsafe == [] and outcomes == {streams[0]: "ok"}


def test_auth_failed_wins_over_an_off_pin_transcript_and_is_not_retried(ctx, monkeypatch):
    off = _pin(ok=False, violations=[{"file": "t", "line": 1, "where": "transcript", "model": "claude-other"}])
    w = World(monkeypatch, ctx, outcomes=("auth_failed",), pins=[off])
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("infra-auth", "authentication_failed")
    n = w.names()
    assert n.count("turn") == 1 and "commit" not in n and n[-1] == "restore"
    assert n.index("collect") > n.index("turn")          # transcripts still collected as evidence
    assert len(e.value.hand_edit_turns) == 1             # the failed turn is still harness cost


def test_an_off_pin_model_in_a_successful_session_is_a_model_pin_fault_not_retried(ctx, monkeypatch):
    off = _pin(ok=False, violations=[{"file": "t", "line": 1, "where": "transcript", "model": "claude-other"}])
    w = World(monkeypatch, ctx, pins=[off])
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("model-pin", "claude-other")
    assert w.names().count("turn") == 1 and "commit" not in w.names()


def test_a_pin_report_with_no_evidence_is_a_fault_even_when_the_session_succeeded(ctx, monkeypatch):
    World(monkeypatch, ctx, pins=[_pin(ok=False, no_evidence=True)])
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("model-pin", "no-evidence")


def test_a_scope_violation_restores_the_pre_edit_state_and_the_second_try_can_land(ctx, monkeypatch):
    w = World(monkeypatch, ctx, outcomes=("ok", "ok"),
              porcelains=(" M src/cli.py\n M docs/spec.md\n", " M src/cli.py\n"))
    edit = handedit.apply(ctx, STEP1)
    n = w.names()
    assert edit.tries == 2 and len(edit.turns) == 2       # both tries' turns are harness cost
    assert ("restore", "02-pre-edit") in w.calls
    turns = [i for i, x in enumerate(n) if x == "turn"]
    assert turns[0] < n.index("restore") < turns[1]      # the second try starts from the restored pre-edit state
    failed = json.loads((ctx.out / "hand-edit" / "try-1-failed.json").read_text())
    assert (failed["kind"], failed["signature"]) == ("hand-edit", "scope") and "docs/spec.md" in failed["detail"]
    assert w.calls[-1] == ("snapshot", 2)


def test_two_failed_tries_raise_the_last_fault_and_leave_the_pre_edit_state(ctx, monkeypatch):
    w = World(monkeypatch, ctx, outcomes=("ok", "is_error"), porcelains=("",))
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "session")
    assert w.names().count("restore") == 2 and w.calls[-1] == ("restore", "02-pre-edit")
    assert ("snapshot", 2) not in w.calls and len(e.value.hand_edit_turns) == 2
    for k in (1, 2):
        assert (ctx.out / "hand-edit" / f"try-{k}-failed.json").exists()


def test_side_effects_are_cleaned_and_recorded(ctx, monkeypatch):
    w = World(monkeypatch, ctx, porcelains=(" M src/cli.py\n M uv.lock\n?? .pytest_cache/x\n",))
    edit = handedit.apply(ctx, STEP1)
    assert ("remove", [".pytest_cache/x"]) in w.calls and ("checkout", ["uv.lock"]) in w.calls
    assert edit.side_effects["removed"] == [".pytest_cache/x"] and edit.side_effects["restored"] == ["uv.lock"]


def test_a_new_entry_beside_the_repo_in_work_is_removed_and_recorded(ctx, monkeypatch):
    w = World(monkeypatch, ctx)
    real = w.porcelains

    def porcelain(p_):
        (ctx.paths.work / "notes.md").write_text("teammate scribbles")   # created during the session
        return real.pop(0)
    monkeypatch.setattr(handedit.gitops, "porcelain", porcelain)
    edit = handedit.apply(ctx, STEP1)
    assert not (ctx.paths.work / "notes.md").exists()
    assert edit.side_effects["removed_beside_repo"] == ["notes.md"]


def test_a_failed_probe_is_a_probe_fault(ctx, monkeypatch):
    bad = '{"env_default":false,"flag_wins":true,"unchanged_without_env":true}\n'
    World(monkeypatch, ctx, outcomes=("ok", "ok"), porcelains=(" M a.py\n",) * 2, probes=(bad, bad))
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "probe") and "env_default" in e.value.detail


def test_unparseable_probe_output_is_a_probe_fault_not_a_crash(ctx, monkeypatch):
    World(monkeypatch, ctx, outcomes=("ok", "ok"), porcelains=(" M a.py\n",) * 2, probes=("", "garbage\n"))
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "probe")


def test_a_changed_step_1_outcome_is_changed_hidden_results(ctx, monkeypatch):
    changed = {**STEP1, "tests.hidden.test_a::t1": "failed"}
    World(monkeypatch, ctx, outcomes=("ok", "ok"), porcelains=(" M a.py\n",) * 2, probes=(GOOD_PROBE,) * 2,
          rechecks=(changed, changed))
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "changed-hidden-results")
    assert "test_a::t1" in e.value.detail


def test_a_harness_flake_in_either_record_is_not_compared(ctx, monkeypatch):
    step1 = {**STEP1, "tests.hidden.test_a::t3": "flaky"}
    recheck = {**STEP1, "tests.hidden.test_a::t3": "passed"}
    World(monkeypatch, ctx, rechecks=(recheck,))
    handedit.apply(ctx, step1)
    rec = json.loads((ctx.out / "hand-edit" / "recheck.json").read_text())
    assert rec["differences"] == {} and rec["not_compared"] == ["tests.hidden.test_a::t3"]


def test_an_unscoreable_recheck_is_a_fault_not_retried(ctx, monkeypatch):
    w = World(monkeypatch, ctx, scoreable=False)
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "recheck-unscoreable")
    assert w.names().count("turn") == 1 and w.calls[-1] == ("restore", "02-pre-edit")


@pytest.mark.parametrize("state, why", [
    (gitops.RepoState("main", True, "h0", "h0", True), "dirty"),
    (gitops.RepoState("feature", False, "h1", "h0", False), "feature"),
])
def test_a_dirty_tree_or_a_branch_other_than_main_stops_before_the_teammate_runs(ctx, monkeypatch, state, why):
    w = World(monkeypatch, ctx, state=state)
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "precondition") and why in e.value.detail
    assert "turn" not in w.names() and "snapshot" not in w.names()


def test_a_commit_that_does_not_land_on_main_as_sam_teammate_is_a_commit_fault(ctx, monkeypatch):
    World(monkeypatch, ctx, outcomes=("ok", "ok"), porcelains=(" M a.py\n",) * 2)
    monkeypatch.setattr(handedit.gitops, "log", lambda p_, a, b: [{"sha": "sha1", "author": "Developer", "subject": "x"}])
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "commit") and "Developer" in e.value.detail


def test_a_hook_that_rejects_the_commit_is_a_commit_fault(ctx, monkeypatch):
    World(monkeypatch, ctx, outcomes=("ok", "ok"), porcelains=(" M a.py\n",) * 2)

    def refuse(p_, who, msg):
        raise RuntimeError("git commit failed in container (1): pre-commit hook said no")
    monkeypatch.setattr(handedit.gitops, "commit_all", refuse)
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, STEP1)
    assert (e.value.kind, e.value.signature) == ("hand-edit", "commit") and "hook said no" in e.value.detail


# ---- detect ---------------------------------------------------------------------------------------------------

def test_detect_writes_the_facts_from_the_end_state(ctx, monkeypatch):
    out = ctx.out
    (out / "turns").mkdir(parents=True)
    with gzip.open(out / "turns" / "arm-a1-001.stream.jsonl.gz", "wt") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "TROUPE_THEATRE is new"}]}}) + "\n")
    (out / "questions.jsonl").write_text(json.dumps({"arm_message": "Should TROUPE_THEATRE stay?"}) + "\n")
    calls = []
    monkeypatch.setattr(handedit.hidden, "prepare", lambda p_, sha, label, o, **k: calls.append((sha, label)) or
                        SimpleNamespace(hidden_copy=o / "c", prep={"hidden": {"ok": True}}))
    monkeypatch.setattr(handedit.hidden, "run_script", lambda p_, c, s: GOOD_PROBE)
    monkeypatch.setattr(handedit.gitops, "grep_files", lambda p_, sha, pat, spec: ["docs/cli.md"])
    monkeypatch.setattr(handedit.gitops, "ls_files", lambda p_, sha: ["src/cli.py", "tests/test_env.py"])
    edit = handedit.HandEdit("sha1", ["src/cli.py", "tests/test_env.py"], [], {}, 1, {})
    facts = handedit.detect(ctx, edit, "end")
    assert calls == [("end", "02-detect")]
    assert facts == {"feature_kept": True, "documented_in": ["docs/cli.md"], "mentioned_in_session": True,
                     "session_mentions": 1, "raised_with_po": True, "teammate_test_kept": True}
    assert json.loads((out / "hand-edit" / "detection.json").read_text()) == facts


def test_detect_reports_a_removed_teammate_test(ctx, monkeypatch):
    monkeypatch.setattr(handedit.hidden, "prepare", lambda p_, sha, label, o, **k:
                        SimpleNamespace(hidden_copy=o / "c", prep={"hidden": {"ok": True}}))
    monkeypatch.setattr(handedit.hidden, "run_script", lambda p_, c, s: GOOD_PROBE)
    monkeypatch.setattr(handedit.gitops, "grep_files", lambda p_, sha, pat, spec: [])
    monkeypatch.setattr(handedit.gitops, "ls_files", lambda p_, sha: ["src/cli.py"])
    edit = handedit.HandEdit("sha1", ["src/cli.py", "tests/test_env.py"], [], {}, 1, {})
    facts = handedit.detect(ctx, edit, "end")
    assert facts["teammate_test_kept"] is False and facts["mentioned_in_session"] is False
