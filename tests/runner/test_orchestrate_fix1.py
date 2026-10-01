"""Task 23 fix round 1: atomic records, Park on the setup path, a strict close-out, the crash window after stepflow
returns, rerun-step at step 1, retest declarations, the HALTED reason, lock ordering, the canary's report, a detached
HEAD set aside, and the consistency check's reach (step N-1's N.b answers; the brief body is the owner's call)."""
import json
import os

import pytest

from runner import checklist, cli, config, faults, fsutil, gitops, orchestrate, paths, preflight
from runner.owner import Park
from runner.paths import Paths

from tests.runner.test_orchestrate import ARMS, PARK, Q, count, dry, progress, real


# ---- 1. atomic writes --------------------------------------------------------------------------------------

def test_a_kill_mid_write_leaves_the_previous_file_intact_and_no_temp_behind(tmp_path, monkeypatch):
    f = tmp_path / "progress.json"
    fsutil.write_json(f, {"v": 1})
    synced = []
    monkeypatch.setattr(fsutil.os, "fsync", lambda fd: synced.append(fd))

    def killed(src, dst):
        raise KeyboardInterrupt("SIGKILL stand-in")
    monkeypatch.setattr(fsutil.os, "replace", killed)
    with pytest.raises(KeyboardInterrupt):
        fsutil.write_json(f, {"v": 2})
    assert json.loads(f.read_text()) == {"v": 1} and synced
    assert [x.name for x in tmp_path.iterdir()] == ["progress.json"]


def test_a_write_that_dies_while_writing_leaves_the_previous_file_intact(tmp_path, monkeypatch):
    f = tmp_path / "rec.json"
    fsutil.write_text(f, "old")
    real_fdopen = os.fdopen

    def dying(fd, *a, **k):
        fh = real_fdopen(fd, *a, **k)
        fh.write("half")
        raise OSError("disk gone")
    monkeypatch.setattr(fsutil.os, "fdopen", dying)
    with pytest.raises(OSError):
        fsutil.write_text(f, "new")
    assert f.read_text() == "old" and [x.name for x in tmp_path.iterdir()] == ["rec.json"]


def test_orchestration_progress_goes_through_the_atomic_writer(fake_orch, monkeypatch):
    seen = []
    real_write = fsutil.write_text
    monkeypatch.setattr(fsutil, "write_text", lambda f, t: seen.append(f.name) or real_write(f, t))
    real(fake_orch)
    assert "progress.json" in seen and "step-01.json" in seen


def test_the_faults_cli_writes_progress_atomically(tmp_state, monkeypatch):
    p = Paths("dry3", "control")
    p.base.mkdir(parents=True)
    p.progress.write_text(json.dumps({"keep": 1}))
    monkeypatch.setattr(fsutil.os, "replace", lambda s, d: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        cli.main(["faults", "declare", "dry3", "control", "4", "x", "--scope", "rerun-step"])
    assert json.loads(p.progress.read_text()) == {"keep": 1}


# ---- 2. Park on the setup path -------------------------------------------------------------------------------

def test_an_owner_checklist_park_ends_setup_as_parked_not_a_crash():
    with pytest.raises(checklist.SetupParked) as e:
        checklist.ask_owner(type("O", (), {"items": lambda self, items: PARK})(), [("OV1", "x")])
    assert e.value.park is PARK


def test_a_parked_setup_reply_ends_setup_as_parked(tmp_state, monkeypatch):
    from runner import session
    from runner.session import TurnResult
    arm = config.load_arm("speckit")                       # one setup agent prompt
    p = Paths("dry7", "speckit")
    out = p.setup_results; out.mkdir(parents=True)
    monkeypatch.setattr(session, "run_turn", lambda t, cred, o, s: TurnResult(
        "s", "ok", "done", {}, None, 0.0, {}, {}, 1.0, [], out / "turns" / "x.gz"))
    owner = type("O", (), {"setup_reply": lambda self, text: PARK})()
    st = type("S", (), {"net": "none"})()
    with pytest.raises(checklist.SetupParked):
        checklist._agent_turns(p, arm, "dry7", None, owner, st, out)


def test_a_parked_setup_parks_the_arm_is_recorded_and_is_redone_next_time(fake_orch, monkeypatch):
    calls = []

    def run_setup(pass_, arm, cred, owner):
        Paths(pass_, arm).base.mkdir(parents=True, exist_ok=True)
        calls.append(arm)
        if len(calls) == 1:
            raise checklist.SetupParked(PARK)
        return checklist.SetupResult([], {}, True, 0.0)
    monkeypatch.setattr(checklist, "run_setup", run_setup)
    f = paths.RESULTS / "pass1" / "order.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"seed": 1, "rule": "t", "order": ["control"]}))
    r = orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    assert r["parked"] == [{"arm": "control", "step": 0, "run": None, "what": "setup"}]
    assert (Paths("pass1", "control").setup_results / "parked.json").exists()
    log = (paths.RESULTS / "pass1" / "run-log.jsonl").read_text()
    assert '"what": "setup"' in log
    orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    assert calls == ["control", "control"] and ("control", 7, "b") in fake_orch.runs()


def test_the_setup_cli_reports_a_park_and_exits_1(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (None, None))

    def parked(*a, **k):
        raise checklist.SetupParked(PARK)
    monkeypatch.setattr(orchestrate, "setup", parked)
    assert cli.main(["setup", "pass1", "control"]) == 1
    assert "parked" in capsys.readouterr().out


# ---- 3. a strict close-out ----------------------------------------------------------------------------------------

@pytest.fixture
def finished(fake_orch, monkeypatch):
    from runner import secrets
    real(fake_orch)
    for a in ARMS:
        (Paths("pass1", a).results / "repo.bundle").write_bytes(b"# v2 git bundle\n")
    env = type("E", (), {"found": [], "orch": fake_orch})
    monkeypatch.setattr(secrets, "scan_tree", lambda root, lits=(): list(env.found))
    return env


def test_close_out_passes_only_when_everything_is_confirmed(finished):
    assert orchestrate.close_out("pass1", finished.orch.owner).exists()


def test_close_out_refuses_with_secret_findings(finished):
    from runner import secrets
    finished.found = [secrets.Finding("pass1/control/03/x.gz", "github-pat", 2)]
    with pytest.raises(orchestrate.NotReady, match="secret"):
        orchestrate.close_out("pass1", finished.orch.owner)
    assert "FINDINGS" in (paths.RESULTS / "pass1" / "close-out.md").read_text()


def test_close_out_refuses_with_a_missing_bundle(finished):
    (Paths("pass1", "control").results / "repo.bundle").unlink()
    with pytest.raises(orchestrate.NotReady, match="bundle"):
        orchestrate.close_out("pass1", finished.orch.owner)


def test_close_out_refuses_a_parked_or_refused_pat_revocation(finished):
    finished.orch.owner.items_answer = lambda items: PARK
    with pytest.raises(orchestrate.NotReady, match="PAT"):
        orchestrate.close_out("pass1", finished.orch.owner)
    finished.orch.owner.items_answer = lambda items: {i: (i != "pat-control", "", 0.0) for i, _ in items}
    with pytest.raises(orchestrate.NotReady, match="pat-control"):
        orchestrate.close_out("pass1", finished.orch.owner)


def test_close_out_refuses_until_publishing_finished(finished):
    p = Paths("pass1", "openspec")
    prog = json.loads(p.progress.read_text())
    prog["finished"]["published"] = None
    p.progress.write_text(json.dumps(prog))
    with pytest.raises(orchestrate.NotReady, match="publish"):
        orchestrate.close_out("pass1", finished.orch.owner)


# ---- 4. the crash window after stepflow returns ---------------------------------------------------------------

def _as_killed(pass_, arm, step, run):
    """What a SIGKILL leaves: the run still `running`, no restore flagged."""
    p = Paths(pass_, arm)
    prog = json.loads(p.progress.read_text())
    prog["steps"][str(step)][run]["status"] = "running"
    prog["steps"][str(step)]["restore_needed"] = False
    p.progress.write_text(json.dumps(prog))


@pytest.mark.parametrize("run", ["a", "b"])
def test_a_run_that_stepflow_finished_before_the_kill_is_not_run_again(fake_orch, run):
    fake_orch.crash_after.add(("dryrun", 3, run))
    with pytest.raises(KeyboardInterrupt):
        dry(fake_orch)
    _as_killed("dry7", "dryrun", 3, run)
    assert dry(fake_orch) == {"completed": True}
    assert count(fake_orch, ("run_step", "dryrun", 3, run)) == 1
    assert progress("dry7", "dryrun")["steps"]["3"][run]["status"] == ("discovered" if run == "a" else "done")


def test_a_finished_discovery_run_is_still_reset_to_its_snapshot(fake_orch):
    fake_orch.crash_after.add(("dryrun", 3, "a"))
    with pytest.raises(KeyboardInterrupt):
        dry(fake_orch)
    _as_killed("dry7", "dryrun", 3, "a")
    fake_orch.calls.clear()
    dry(fake_orch)
    assert fake_orch.calls.index(("restore", "dryrun", 3)) < fake_orch.calls.index(("run_step", "dryrun", 3, "b"))


def test_a_run_without_stepflows_completion_record_is_run_again(fake_orch):
    fake_orch.outcome[("dryrun", 3, "b")] = ["boom"]
    with pytest.raises(RuntimeError):
        dry(fake_orch)
    _as_killed("dry7", "dryrun", 3, "b")
    dry(fake_orch)
    assert count(fake_orch, ("run_step", "dryrun", 3, "b")) == 2


# ---- 5. rerun-step at step 1 ------------------------------------------------------------------------------------

def test_a_rerun_from_step1_drops_the_old_hand_edits_teammate_cost(fake_orch):
    dry(fake_orch)
    assert cli.main(["faults", "declare", "dry7", "dryrun", "1", "wrong-brief", "--scope", "rerun-step"]) == 0
    dry(fake_orch)
    assert [t.cost_usd for t in fake_orch.extras[("dryrun", 2, "b")]["teammate"]] == [0.25]
    assert count(fake_orch, ("hand_edit", "dryrun", 2)) == 2


# ---- 6. retest declarations ---------------------------------------------------------------------------------------

def test_a_retest_is_honoured_only_for_its_own_pass(fake_orch):
    real(fake_orch)
    (Paths("pass1", "control").step(2) / "git.json").write_text(json.dumps({"sha_after": "sha-2"}))
    faults._enter("pass1", {"pass": "canary", "arm": "control", "step": 2, "run": None, "attempt": None,
                            "kind": "manual", "signature": "other-pass", "detail": "x", "action": "retest",
                            "scope": "retest"})                         # a ledger line naming another pass
    fake_orch.calls.clear()
    real(fake_orch)
    assert not [c for c in fake_orch.calls if c[0] == "prepare"]


def test_a_retest_of_a_step_that_never_ran_is_refused_clearly_and_never_blocks(fake_orch):
    fake_orch.make("dryrun", pass_="dry7")
    (paths.RESULTS / "dry7").mkdir(parents=True, exist_ok=True)
    faults.declare("dry7", "dryrun", 5, "too-early", "retest")
    assert dry(fake_orch) == {"completed": True}
    refused = json.loads((Paths("dry7", "dryrun").results / "retest-refused.json").read_text())
    assert refused[0]["step"] == 5 and "declare it again" in refused[0]["why"]
    fake_orch.calls.clear()
    dry(fake_orch)                                                      # refused once, then out of the way
    assert not [c for c in fake_orch.calls if c[0] == "prepare"]


# ---- 7. the HALTED reason --------------------------------------------------------------------------------------

def test_halted_names_a_suite_resource_halt(tmp_state, capsys):
    faults.halt("pass1", "suite-resource:3: 2 arms exhausted resources at step 3", {"kind": "suite-resource"})
    assert cli.main(["status"]) == 1
    out = capsys.readouterr().out
    assert "suite-resource:3" in out and "occurred twice" not in out


def test_halted_names_the_repeated_fault(tmp_state, capsys):
    for _ in (1, 2):
        faults.record(faults.HarnessFault("model-pin", "claude-haiku-4-5"), "pass1", "control", 1, 1)
    assert cli.main(["status"]) == 1
    assert "same harness fault twice: model-pin:claude-haiku-4-5" in capsys.readouterr().out


def test_the_run_command_prints_the_halt_reason(tmp_state, monkeypatch, capsys):
    from runner import stepflow
    monkeypatch.setattr(cli, "_real_cred_owner", lambda: (None, None))

    def halt(pass_, cred, owner):
        faults.halt("pass1", "suite-resource:4: 2 arms", {})
        raise stepflow.Halt(faults.halted("pass1"))
    monkeypatch.setattr(orchestrate, "run_pass", halt)
    assert cli.main(["run-pass", "pass1"]) == 2
    assert "suite-resource:4" in capsys.readouterr().out


# ---- 8. lock ordering ------------------------------------------------------------------------------------------

def _lock_is_held():
    try:
        with preflight.lock():
            return False
    except checklist.NotReady:
        return True


def test_the_lock_is_held_during_the_prechecks(fake_orch, monkeypatch):
    held = []
    monkeypatch.setattr(checklist, "require_clean_green", lambda p: held.append(_lock_is_held()))
    monkeypatch.setattr(preflight, "check_images", lambda arm, p: held.append(_lock_is_held()))
    dry(fake_orch)
    assert held and all(held)


def test_the_lock_is_held_during_setup(fake_orch, monkeypatch):
    held = []

    def run_setup(pass_, arm, cred, owner):
        held.append(_lock_is_held())
        Paths(pass_, arm).base.mkdir(parents=True)
        return checklist.SetupResult([], {}, True, 0.0)
    monkeypatch.setattr(checklist, "run_setup", run_setup)
    f = paths.RESULTS / "pass1" / "order.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"seed": 1, "rule": "t", "order": ["control"]}))
    orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    assert held == [True, True]


# ---- 9. the canary's report ------------------------------------------------------------------------------------

def test_a_canary_that_stops_early_is_reported_as_stopped(fake_orch):
    fake_orch.make("control", pass_="canary")
    fake_orch.outcome[("control", 1, "b")] = ["stopped"]
    r = orchestrate.run_arm("canary", "control", fake_orch.cred, fake_orch.owner, stop_after=2)
    assert r == {"stopped_at": 1}


# ---- 10. a detached HEAD set aside ------------------------------------------------------------------------------

def test_a_detached_head_gets_a_branch_first_so_its_commits_stay_reachable(monkeypatch):
    calls = []
    monkeypatch.setattr(gitops, "git", lambda p, *a, write=False, env=None, **k: calls.append(a) or
                        type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})())
    monkeypatch.setattr(gitops, "state", lambda p: gitops.RepoState("", False, "dead", "main1", False))
    rec = gitops.set_aside_to_main(Paths("pass1", "control"), "x", label="02")
    assert calls[0][:2] == ("branch", rec["aside_branch"]) and rec["aside_branch"].startswith("bakeoff/aside-02-")
    assert calls[-1] == ("checkout", "-q", "main") and rec["checked_out_main"] is True


# ---- 11. the consistency check's reach ------------------------------------------------------------------------------

def test_a_brief_answer_dated_step_n_minus_1_after_its_check_is_shown_at_step_ns_check(fake_orch):
    # N.b no longer appends to the brief (the fallback, owner 2026-10-01); the reach stays for an answer that does
    # land in the brief at step N-1 after its check (as N.b escalations could before)
    fake_orch.escalate_b[("control", 1)] = ("Asked during 1.b?", "Yes.")
    real(fake_orch)
    [items] = fake_orch.owner.item_calls
    assert "Asked during 1.b?" in items[0][1] and "step 1" in items[0][1]
    rec = json.loads((paths.RESULTS / "pass1" / "consistency" / "step-02.json").read_text())
    assert rec["status"] == "confirmed"


def test_the_owner_is_told_the_brief_body_is_their_call(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    real(fake_orch)
    [items] = fake_orch.owner.item_calls
    assert "po-brief.md" in items[0][1] and "your call" in items[0][1]


def test_close_out_asks_for_every_discovery_pat_to_be_revoked_too(finished):              # final fix batch A3
    asked = []
    finished.orch.owner.items_answer = lambda items: asked.extend(i for i, _ in items) or \
        {i: (True, "", 0.0) for i, _ in items}
    orchestrate.close_out("pass1", finished.orch.owner)
    assert {"pat-control", "pat-disc-control", "pat-openspec", "pat-disc-openspec"} <= set(asked)
    text = (paths.RESULTS / "pass1" / "close-out.md").read_text()
    assert "bakeoff-gh-pass1-disc-control" in text


# ---- OWNER: close-out publishes each arm to a PRIVATE troupe-run/bakeoff-specs-<arm>; step-7 escalations shown --------

def test_close_out_creates_the_final_repo_private_and_publishes_the_arms_history(finished):
    orchestrate.close_out("pass1", finished.orch.owner)
    for a in ARMS:
        slug = f"troupe-run/bakeoff-specs-{a}"
        assert finished.orch.gh_repos[slug] == "PRIVATE"
        assert ("gh", "repo", "create", slug) in finished.orch.calls and ("publish", a, slug) in finished.orch.calls
    text = (paths.RESULTS / "pass1" / "close-out.md").read_text()
    assert "troupe-run/bakeoff-specs-control: created private, published" in text


def test_close_out_reuses_an_existing_private_repo_and_never_publishes_to_a_public_one(finished):
    finished.orch.gh_repos.update({"troupe-run/bakeoff-specs-control": "PRIVATE",
                                   "troupe-run/bakeoff-specs-openspec": "PUBLIC"})
    with pytest.raises(orchestrate.NotReady, match="public"):
        orchestrate.close_out("pass1", finished.orch.owner)
    assert ("gh", "repo", "create", "troupe-run/bakeoff-specs-control") not in finished.orch.calls
    assert ("publish", "control", "troupe-run/bakeoff-specs-control") in finished.orch.calls
    assert not [c for c in finished.orch.calls if c[:2] == ("publish", "openspec") and len(c) == 3]
    assert finished.orch.gh_repos["troupe-run/bakeoff-specs-openspec"] == "PUBLIC"      # never changed by us


def test_close_out_publishes_each_arm_once(finished):
    orchestrate.close_out("pass1", finished.orch.owner)
    orchestrate.close_out("pass1", finished.orch.owner)
    assert len([c for c in finished.orch.calls if c[:2] == ("publish", "control") and len(c) == 3]) == 1


def test_close_out_shows_the_step7_nb_escalations_for_the_owner(finished):
    q = Paths("pass1", "control").step(7) / "questions.jsonl"
    q.write_text(json.dumps({"escalated": ["Remote include timeout?"], "reply": "30 seconds."}) + "\n")
    asked = []
    finished.orch.owner.items_answer = lambda items: asked.extend(items) or {i: (True, "", 0.0) for i, _ in items}
    orchestrate.close_out("pass1", finished.orch.owner)
    esc = [t for i, t in asked if i.startswith("esc7-")]
    assert esc and "Remote include timeout? → 30 seconds." in esc[0] and "control" in esc[0]
    assert "Remote include timeout?" in (paths.RESULTS / "pass1" / "close-out.md").read_text()
    finished.orch.owner.items_answer = lambda items: {i: (not i.startswith("esc7-"), "", 0.0) for i, _ in items}
    with pytest.raises(orchestrate.NotReady, match="esc7-control"):
        orchestrate.close_out("pass1", finished.orch.owner)


# ---- owner, 2026-10-01: N.b escalations get the fallback; the next step's check shows them (informational) ----------

FB = "Remote include timeout?"


def _fb_record(step):
    return json.loads((paths.RESULTS / "pass1" / "consistency" / f"step-{step:02d}.json").read_text())


def test_step_ns_fallback_questions_are_shown_at_step_n_plus_1s_check_without_a_prompt_and_recorded(fake_orch):
    fake_orch.fallback_b[("control", 1)] = [FB]
    real(fake_orch)
    assert fake_orch.owner.item_calls == []                     # nothing to confirm: informational only
    shown = [t for t in fake_orch.owner.informed if FB in t]
    assert len(shown) == 1 and "control" in shown[0] and "step 1" in shown[0] and "po-brief.md" in shown[0]
    rec = _fb_record(2)
    assert rec["status"] == "nothing-new"
    assert rec["fallbacks"] == [{"arm": "control", "step": 1, "question": FB}]
    md = (paths.RESULTS / "pass1" / "consistency" / "step-02.md").read_text()
    assert "answered by the fallback in step 1's scored run" in md and FB in md and "control" in md
    assert _fb_record(1).get("fallbacks") == [] and _fb_record(3).get("fallbacks") == []


def test_fallbacks_are_shown_alongside_new_escalations_but_are_not_items_to_confirm(fake_orch):
    fake_orch.fallback_b[("openspec", 1)] = [FB]
    fake_orch.escalate[("control", 2)] = (Q, "Yes.")
    real(fake_orch)
    [items] = fake_orch.owner.item_calls
    assert len(items) == 1 and FB not in items[0][1] and Q in items[0][1]
    assert any(FB in t for t in fake_orch.owner.informed)
    rec = _fb_record(2)
    assert rec["status"] == "confirmed" and rec["fallbacks"] == [{"arm": "openspec", "step": 1, "question": FB}]


def test_the_last_steps_fallbacks_are_listed_in_the_close_out_without_blocking_it(finished):
    q = Paths("pass1", "control").step(7) / "questions.jsonl"
    q.write_text(json.dumps({"kind": "question", "escalated": [FB], "fallback": [FB], "answered_by": "fallback",
                             "reply": "The brief doesn't cover this."}) + "\n")
    asked = []
    finished.orch.owner.items_answer = lambda items: asked.extend(i for i, _ in items) or \
        {i: (True, "", 0.0) for i, _ in items}
    orchestrate.close_out("pass1", finished.orch.owner)                       # not refused
    assert not [i for i in asked if i.startswith("esc7-")]                    # not an item to confirm
    text = (paths.RESULTS / "pass1" / "close-out.md").read_text()
    sec = text.split("step 7 N.b questions answered by the fallback", 1)[1]
    assert f"control: {FB}" in sec.split("\n- brief at close")[0]
