"""Task 23: orchestration — the arm order, the step-major N.a / consistency check / N.b run (owner, 2026-09-29),
resume and restore after a park/pause/halt/crash, the step-2 hand edit, step 5's two requests, step 6's issue (with
the substitute-bug fallback), the suite-resource halt, per-step secret scans, the owner's step review, the end of an
arm (bundle, arm-result, private publish), declared re-runs and re-tests, setup once per arm, close-out, status.

Everything effectful is faked by the `fake_orch` fixture (conftest): stepflow, git, snapshots, the tracker, the
scans and the hidden tests. Docker-backed pieces have their own tests."""
import json

import pytest

from runner import checklist, cli, config, faults, orchestrate, paths, stepflow
from runner.owner import Park
from runner.paths import Paths
from runner.secrets import own_pat_values as REAL_OWN            # before fake_orch replaces it

PARK = Park("x", "context", "unattended", 0.0, 0.0)
ARMS = ("openspec", "control")


def real(env, arms=ARMS):
    env.make(*arms, pass_="pass1")
    f = paths.RESULTS / "pass1" / "order.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"seed": 1, "rule": "test", "order": list(arms)}))
    return orchestrate.run_pass("pass1", env.cred, env.owner)


def dry(env, **kw):
    env.make("dryrun", pass_="dry7")
    return orchestrate.run_arm("dry7", "dryrun", env.cred, env.owner, **kw)


def progress(pass_, arm):
    return json.loads(Paths(pass_, arm).progress.read_text())


def count(env, call):
    return env.calls.count(call)


# ---- the order (OD13, owner: bmad parked) --------------------------------------------------------------------

def test_order_is_reproducible_from_the_seed_control_never_goes_first_and_only_active_arms_run(tmp_state):
    for seed in range(50):
        o = orchestrate.order("pass1", seed)
        assert o == orchestrate.order("pass1", seed) and o[0] != "control"
        assert sorted(o) == sorted(config.active_arms()) and "bmad" not in o
    rec = json.loads((paths.RESULTS / "pass1" / "order.json").read_text())
    assert rec["seed"] == 49 and rec["order"] == orchestrate.order("pass1", 49)


def test_an_order_without_a_seed_draws_one_and_records_it_so_it_can_be_reproduced(tmp_state):
    o = orchestrate.order("pass1")
    seed = json.loads((paths.RESULTS / "pass1" / "order.json").read_text())["seed"]
    assert isinstance(seed, int) and orchestrate.order("pass1", seed) == o


def test_the_canary_orders_control_alone(tmp_state):
    assert orchestrate.order("canary") == ["control"]


def test_there_is_no_second_real_pass(tmp_state):          # owner 2026-09-29: N.a/N.b inside each step
    with pytest.raises(orchestrate.NotReady, match="pass1"):
        orchestrate.order("pass2")


# ---- the step-major run ------------------------------------------------------------------------------------------

def test_each_step_runs_every_arms_discovery_then_the_check_then_every_arms_scored_run(fake_orch):
    real(fake_orch)
    want = [(a, n, r) for n in range(1, 8) for r in ("a", "b") for a in ARMS]
    assert fake_orch.runs() == want


def test_discovery_evidence_goes_under_a_and_the_scored_run_under_the_step(fake_orch):
    real(fake_orch)
    p = Paths("pass1", "openspec")
    assert fake_orch.ctxs[("openspec", 3, "a")].out == p.step(3) / "a"
    assert fake_orch.ctxs[("openspec", 3, "b")].out == p.step(3)
    assert (p.step(3) / "a" / "handoff.md").exists() and (p.step(3) / "handoff.md").exists()


def test_the_scored_run_starts_from_the_discovery_runs_snapshot_and_sha(fake_orch):
    real(fake_orch)
    for n in range(1, 8):
        a, b = fake_orch.ctxs[("control", n, "a")], fake_orch.ctxs[("control", n, "b")]
        assert (a.snapshot, a.sha_before) == (b.snapshot, b.sha_before) == (n, a.sha_before)
    assert count(fake_orch, ("snapshot", "control", 4)) == 1          # one pre-step snapshot per step


def test_the_scored_run_builds_on_the_previous_scored_run(fake_orch):
    real(fake_orch)
    assert fake_orch.ctxs[("openspec", 4, "a")].sha_before == "sha-3"


def test_a_run_sweeps_leftover_containers_before_anything_else(fake_orch):
    real(fake_orch)
    assert fake_orch.calls[0] == ("sweep",)


# ---- step 2: the hand edit ---------------------------------------------------------------------------------------

def test_the_hand_edit_is_applied_once_before_2a_and_both_runs_start_from_its_commit(fake_orch):
    real(fake_orch)
    c = fake_orch.calls
    assert count(fake_orch, ("hand_edit", "openspec", 2)) == 1
    assert c.index(("hand_edit", "openspec", 2)) < c.index(("run_step", "openspec", 2, "a"))
    assert fake_orch.ctxs[("openspec", 2, "a")].sha_before == fake_orch.ctxs[("openspec", 2, "b")].sha_before == "edit-sha"
    assert ("snapshot", "openspec", 2) not in c                         # apply takes snapshot(2) itself


def test_the_teammates_turns_are_harness_cost_of_the_scored_run_only(fake_orch):
    real(fake_orch)
    b = fake_orch.extras[("openspec", 2, "b")]
    assert list(b) == ["teammate"] and [t.cost_usd for t in b["teammate"]] == [0.25]
    assert not fake_orch.extras[("openspec", 2, "a")]                   # never counted twice


def test_leftovers_after_step1_are_set_aside_so_the_teammate_commits_on_a_clean_main(fake_orch):
    fake_orch.state.update(branch="feature", dirty=True)
    dry(fake_orch)
    c = fake_orch.calls
    assert c.index(("set_aside", "dryrun")) < c.index(("hand_edit", "dryrun", 2))
    rec = json.loads((Paths("dry7", "dryrun").step(2) / "hand-edit" / "pre-edit-state.json").read_text())
    assert rec["branch"] == "feature" and rec["dirty"] is True


def test_a_clean_main_is_not_touched(fake_orch):
    dry(fake_orch)
    assert ("set_aside", "dryrun") not in fake_orch.calls


def test_detection_reads_the_scored_runs_arm_streams_and_transcripts_at_its_end(fake_orch):
    dry(fake_orch)
    [d] = [c for c in fake_orch.calls if c[0] == "detect"]
    assert d == ("detect", "dryrun", "sha-2", ("transcripts/a1/projects/s.jsonl.gz", "turns/arm-a1-001.stream.jsonl.gz"))
    a = json.loads((Paths("dry7", "dryrun").step(2) / "hand-edit" / "detection-a.json").read_text())
    assert a["session_mentions"] == 0 and "raised_with_po" in a                  # 2.a recorded, not scored


def test_a_parked_hand_edit_is_retried_from_the_pre_edit_snapshot(fake_orch, monkeypatch):
    real_edit = stepflow.hand_edit
    tries = []

    def edit(ctx, step1):
        tries.append(1)
        if len(tries) == 1:                      # as apply: the pre-edit snapshot is taken before the teammate
            ctx.paths.snapshots.mkdir(parents=True, exist_ok=True)
            (ctx.paths.snapshots / "step-02-pre-edit.tar").write_bytes(b"")
            raise stepflow.Paused("parked", park=PARK)
        return real_edit(ctx, step1)
    monkeypatch.setattr(stepflow, "hand_edit", edit)
    assert "parked" in dry(fake_orch)
    assert ("run_step", "dryrun", 2, "a") not in fake_orch.calls
    dry(fake_orch)
    c = fake_orch.calls
    assert c.index(("restore", "dryrun", "02-pre-edit")) < c.index(("hand_edit", "dryrun", 2))


# ---- step 5: two requests; the PO gets the full contract ----------------------------------------------------------

def test_step5_hands_cr_b_as_a_later_message_in_both_runs_and_the_po_the_full_contract(fake_orch):
    real(fake_orch)
    contract = (paths.REPO_ROOT / "scenario" / "contract.md").read_text()
    for run in ("a", "b"):
        ctx = fake_orch.ctxs[("openspec", 5, run)]
        assert len(ctx.later_messages) == 1 and "## CR-B" in ctx.later_messages[0]
        assert ctx.contract == contract and "## CR-B" in ctx.step_brief
    assert fake_orch.ctxs[("openspec", 4, "b")].later_messages == []


# ---- step 6: the issue -------------------------------------------------------------------------------------------

def test_step6_files_the_bug_before_its_snapshot_and_hands_the_arm_the_issue_ref(fake_orch):
    dry(fake_orch)
    c = fake_orch.calls
    assert c.index(("create_bug", "dryrun", None)) < c.index(("snapshot", "dryrun", 6)) < \
        c.index(("run_step", "dryrun", 6, "a"))
    assert "A bug has been reported in our tracker: troupe-run/x#1." in fake_orch.firsts[("dryrun", 6, "b")]
    assert count(fake_orch, ("create_bug", "dryrun", None)) == 1


def test_an_issue_the_arm_touched_in_6a_is_superseded_and_6b_gets_a_fresh_one(fake_orch):
    fake_orch.outcome[("dryrun", 6, "a")] = ["touch"]
    dry(fake_orch)
    assert ("supersede", "dryrun", "troupe-run/x#1") in fake_orch.calls
    assert "troupe-run/x#2" in fake_orch.firsts[("dryrun", 6, "b")]


def test_an_untouched_issue_is_kept_for_6b(fake_orch):
    dry(fake_orch)
    assert not [c for c in fake_orch.calls if c[0] == "supersede"]
    assert "troupe-run/x#1" in fake_orch.firsts[("dryrun", 6, "b")]


def test_a_harness_rerun_inside_step6_supersedes_a_touched_issue_and_names_the_new_one(fake_orch):
    fake_orch.outcome[("dryrun", 6, "b")] = ["touch-harness-rerun"]
    dry(fake_orch)
    assert ("supersede", "dryrun", "troupe-run/x#1") in fake_orch.calls
    assert "troupe-run/x#2" in fake_orch.restore_message


def test_a_harness_rerun_inside_step6_keeps_an_untouched_issue(fake_orch):
    fake_orch.outcome[("dryrun", 6, "b")] = ["harness-rerun"]
    dry(fake_orch)
    assert fake_orch.restore_message is None and not [c for c in fake_orch.calls if c[0] == "supersede"]


def test_the_round_trip_facts_and_the_tracker_snapshot_are_taken_after_6b(fake_orch):
    dry(fake_orch)
    [rt] = [c for c in fake_orch.calls if c[0] == "round_trip"]
    assert rt == ("round_trip", "dryrun", "troupe-run/x#1", "sha-5", "sha-6")
    assert (Paths("dry7", "dryrun").step(6) / "tracker-round-trip.json").exists()
    assert all((Paths("dry7", "dryrun").step(n) / "tracker.json").exists() for n in range(1, 8))


def test_the_planted_bug_is_prechecked_on_the_step5_commit(fake_orch):
    dry(fake_orch)
    assert ("prepare", "dryrun", "06-precheck", "refs/heads/main") in fake_orch.calls
    pc = json.loads((Paths("dry7", "dryrun").step(6) / "precheck" / "precheck.json").read_text())
    assert pc["planted_already_passes"] is False and fake_orch.owner.substitutes == []


def test_a_bug_that_already_passes_lets_the_owner_substitute_one_whose_test_fails_first(fake_orch):
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("substitute", "Sub title", "Sub body", "why", "def test_x(): 0", 1.0)]
    fake_orch.acceptance = [{"outcome": "failed", "tests": {"m::x": "failed"}}]
    dry(fake_orch)
    d = Paths("dry7", "dryrun").step(6) / "substitute"
    assert ("create_bug", "dryrun", "Sub title") in fake_orch.calls
    assert (d / "test_substitute.py").read_text() == "def test_x(): 0" and "why" in (d / "why.md").read_text()
    assert json.loads((d / "acceptance.json").read_text())["outcome"] == "failed"


def test_a_substitute_whose_test_already_passes_is_refused_and_the_owner_asked_again(fake_orch):
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("substitute", "A", "a", "w", "t1", 1.0),
                                          ("substitute", "B", "b", "w", "t2", 1.0)]
    fake_orch.acceptance = [{"outcome": "passed", "tests": {}}, {"outcome": "failed", "tests": {}}]
    dry(fake_orch)
    assert ("create_bug", "dryrun", "B") in fake_orch.calls and ("create_bug", "dryrun", "A") not in fake_orch.calls
    assert "the bug is not there" in fake_orch.owner.substitutes[1]


def test_keeping_the_planted_bug_files_it_as_usual(fake_orch):
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("planted", "", "", "", "", 0.0)]
    dry(fake_orch)
    assert ("create_bug", "dryrun", None) in fake_orch.calls


def test_a_parked_substitute_decision_parks_the_arm_before_anything_is_filed(fake_orch):
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [PARK]
    assert "parked" in dry(fake_orch)
    assert not [c for c in fake_orch.calls if c[0] == "create_bug"]


def test_an_owner_park_while_filing_the_issue_is_never_taken_as_yes(fake_orch):
    fake_orch.owner.confirm_answer = lambda text: PARK if "step-6 issue" in text else True
    assert "parked" in dry(fake_orch)
    assert not [c for c in fake_orch.calls if c[0] == "create_bug"]


# ---- parks, pauses, halts and crashes: the existing snapshot is restored before any re-run (I-2) ------------------

def test_a_parked_discovery_run_moves_on_to_the_next_arm_and_holds_the_phase(fake_orch):
    fake_orch.outcome[("openspec", 1, "a")] = ["parked"]
    r = real(fake_orch)
    assert fake_orch.runs() == [("openspec", 1, "a"), ("control", 1, "a")]
    assert r["parked"] == [{"arm": "openspec", "step": 1, "run": "a", "what": "run"}]
    assert fake_orch.owner.item_calls == []                             # no consistency check yet
    log = [json.loads(l) for l in (paths.RESULTS / "pass1" / "run-log.jsonl").read_text().splitlines()]
    assert any(e["event"] == "parked" and e["arm"] == "openspec" for e in log)


def test_a_parked_run_is_restored_to_its_existing_snapshot_and_its_evidence_kept_aside(fake_orch):
    fake_orch.outcome[("openspec", 1, "a")] = ["parked"]
    real(fake_orch)
    before = fake_orch.ctxs[("openspec", 1, "a")].sha_before
    fake_orch.calls.clear()
    real(fake_orch)
    c = fake_orch.calls
    assert c.index(("restore", "openspec", 1)) < c.index(("run_step", "openspec", 1, "a"))
    assert ("snapshot", "openspec", 1) not in c                         # never re-snapshotted once started
    assert fake_orch.ctxs[("openspec", 1, "a")].sha_before == before
    assert (Paths("pass1", "openspec").step(1) / "a-interrupted-1" / "parked.json").exists()
    assert ("run_step", "control", 1, "a") not in c                     # done runs are not repeated


def test_a_halt_propagates_and_the_resumed_run_restores_first(fake_orch):
    fake_orch.outcome[("dryrun", 1, "b")] = ["halt"]
    with pytest.raises(stepflow.Halt):
        dry(fake_orch)
    assert progress("dry7", "dryrun")["steps"]["1"]["b"]["status"] == "halted"
    fake_orch.calls.clear()
    dry(fake_orch)
    c = fake_orch.calls
    assert c.index(("restore", "dryrun", 1)) < c.index(("run_step", "dryrun", 1, "b"))
    assert (Paths("dry7", "dryrun").step(1) / "b-interrupted-1").is_dir()
    assert (Paths("dry7", "dryrun").step(1) / "a" / "discovery.json").exists()        # N.a evidence stays


def test_an_owner_who_declines_a_harness_fix_stops_the_whole_run(fake_orch):
    fake_orch.outcome[("openspec", 1, "a")] = ["paused"]
    r = real(fake_orch)
    assert fake_orch.runs() == [("openspec", 1, "a")] and "declined" in r


def test_a_park_inside_a_harness_fault_prompt_parks_the_arm_and_moves_on(fake_orch):
    fake_orch.outcome[("openspec", 1, "a")] = ["paused-park"]
    r = real(fake_orch)
    assert ("control", 1, "a") in fake_orch.runs() and r["parked"][0]["arm"] == "openspec"


def test_a_crash_mid_run_is_restored_before_the_run_is_tried_again(fake_orch):
    fake_orch.outcome[("dryrun", 3, "a")] = ["boom"]
    with pytest.raises(RuntimeError, match="crash"):
        dry(fake_orch)
    assert progress("dry7", "dryrun")["steps"]["3"]["restore_needed"] is True
    fake_orch.calls.clear()
    dry(fake_orch)
    assert fake_orch.calls.index(("restore", "dryrun", 3)) < fake_orch.calls.index(("run_step", "dryrun", 3, "a"))


# ---- the consistency check before N.b ------------------------------------------------------------------------

Q = "Should config show print floats exactly as written in the file?"


def test_conflicting_answers_to_the_same_question_are_shown_together_and_flagged(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes, byte for byte.")
    fake_orch.escalate[("control", 1)] = (Q, "No, normalise them.")
    real(fake_orch)
    [items] = fake_orch.owner.item_calls
    assert len(items) == 1
    text = items[0][1]
    assert "CONFLICT" in text and "Yes, byte for byte." in text and "No, normalise them." in text
    assert "openspec" in text and "control" in text
    rec = json.loads((paths.RESULTS / "pass1" / "consistency" / "step-01.json").read_text())
    assert rec["status"] == "confirmed" and rec["rounds"][0]["groups"][0]["conflict"] is True


def test_overlapping_questions_are_flagged_for_the_owner(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    fake_orch.escalate[("control", 1)] = ("Should config show print floats exactly as they are written?", "Yes.")
    real(fake_orch)
    [items] = fake_orch.owner.item_calls
    assert len(items) == 2 and any("OVERLAPS" in t for _, t in items)


def test_the_check_runs_before_any_scored_run_of_the_step(fake_orch):
    fake_orch.escalate[("openspec", 2)] = (Q, "Yes.")
    seen = []
    fake_orch.owner.items_answer = lambda items: (seen.append(list(fake_orch.runs())), {i: (True, "", 0.0) for i, _ in items})[1]
    real(fake_orch)
    assert seen[0][-1] == ("control", 2, "a") and ("openspec", 2, "b") not in seen[0]


def test_a_rejected_answer_waits_for_the_owners_brief_edit_then_rechecks(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    fake_orch.escalate[("control", 1)] = (Q, "No.")
    answers = iter([False, True])
    fake_orch.owner.items_answer = lambda items: {i: (next(answers), "", 0.0) for i, _ in items}

    def edit(text):
        if "Edit" in text:
            fake_orch.brief.write_text(fake_orch.brief.read_text().replace("**A:** No.", "**A:** Yes."))
        return True
    fake_orch.owner.confirm_answer = edit
    real(fake_orch)
    rec = json.loads((paths.RESULTS / "pass1" / "consistency" / "step-01.json").read_text())
    assert len(rec["rounds"]) == 2 and rec["edited"] is True and rec["rounds"][1]["groups"][0]["conflict"] is False
    assert any(c[0] == "commit-brief" for c in fake_orch.calls)         # real pass: the brief is committed


def test_the_check_parks_when_the_owner_is_away_and_no_scored_run_starts(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    fake_orch.owner.items_answer = lambda items: PARK
    r = real(fake_orch)
    assert not [x for x in fake_orch.runs() if x[2] == "b"] and r["parked"][0]["what"] == "consistency"
    fake_orch.owner.items_answer = lambda items: {i: (True, "", 0.0) for i, _ in items}
    real(fake_orch)
    assert ("openspec", 1, "b") in fake_orch.runs()


def test_no_new_answers_needs_no_owner_prompt_but_is_recorded(fake_orch):
    real(fake_orch)
    assert fake_orch.owner.item_calls == []
    rec = json.loads((paths.RESULTS / "pass1" / "consistency" / "step-04.json").read_text())
    assert rec["status"] == "nothing-new"


def test_a_resumed_run_does_not_ask_again_about_steps_whose_scored_runs_are_done(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    state = {"paused": False}

    def review(md):
        if "Step 3 " in md and not state["paused"]:
            state["paused"] = True
            return "pause", 0.0
        return "continue", 0.0
    fake_orch.owner.review_answer = review
    real(fake_orch)
    from runner import po
    po.append_escalation(fake_orch.brief, "Asked during 1.b?", "Yes.", "pass1", "control", 1, source="scripted")
    real(fake_orch)
    assert len(fake_orch.owner.item_calls) == 1


def test_a_crash_inside_the_hand_edit_restarts_it_from_the_pre_edit_snapshot(fake_orch, monkeypatch):
    real_edit = stepflow.hand_edit
    tries = []

    def edit(ctx, step1):
        tries.append(1)
        if len(tries) == 1:
            ctx.paths.snapshots.mkdir(parents=True, exist_ok=True)
            (ctx.paths.snapshots / "step-02-pre-edit.tar").write_bytes(b"")
            raise KeyboardInterrupt
        return real_edit(ctx, step1)
    monkeypatch.setattr(stepflow, "hand_edit", edit)
    with pytest.raises(KeyboardInterrupt):
        dry(fake_orch)
    fake_orch.calls.clear()
    dry(fake_orch)
    c = fake_orch.calls
    assert c.index(("restore", "dryrun", "02-pre-edit")) < c.index(("hand_edit", "dryrun", 2))
    assert count(fake_orch, ("hand_edit", "dryrun", 2)) == 1


def test_answers_from_an_earlier_step_are_not_shown_again(fake_orch):
    fake_orch.escalate[("openspec", 1)] = (Q, "Yes.")
    real(fake_orch)
    assert len(fake_orch.owner.item_calls) == 1


# ---- resource exhaustion across arms (design §9, owner 2026-09-29) -----------------------------------------------

def test_two_arms_exhausting_resources_at_one_step_halt_the_bake_off_as_a_suite_fault(fake_orch):
    fake_orch.resource[("openspec", 3)] = "repeat"
    fake_orch.resource[("control", 3)] = "once"
    with pytest.raises(stepflow.Halt):
        real(fake_orch)
    e = [x for x in faults.entries("pass1") if x.get("kind") == "suite-resource"]
    assert [(x["signature"], x["step"]) for x in e] == [("3", 3)] and faults.halted("pass1")


def test_one_arm_exhausting_resources_is_that_arms_result(fake_orch):
    fake_orch.resource[("openspec", 3)] = "repeat"
    real(fake_orch)
    assert not faults.halted("pass1")


def test_after_the_fix_arms_scored_all_failed_at_that_step_are_rerun(fake_orch):
    fake_orch.resource[("openspec", 3)] = "repeat"
    fake_orch.resource[("control", 3)] = "once"
    with pytest.raises(stepflow.Halt):
        real(fake_orch)
    faults.resume("pass1", "raised the memory limit")
    fake_orch.resource.clear(); fake_orch.calls.clear()
    real(fake_orch)
    runs = fake_orch.runs()
    assert runs[0] == ("openspec", 3, "b") and ("control", 3, "b") not in runs
    assert fake_orch.calls.index(("restore", "openspec", 3)) < fake_orch.calls.index(("run_step", "openspec", 3, "b"))
    assert (Paths("pass1", "openspec").step(3) / "b-superseded-1").is_dir()


# ---- stopped arms -----------------------------------------------------------------------------------------------

def test_a_stopped_arm_runs_no_further_steps_and_keeps_stepflows_arm_result(fake_orch):
    fake_orch.outcome[("dryrun", 3, "b")] = ["stopped"]
    assert dry(fake_orch) == {"stopped_at": 3}
    assert fake_orch.runs()[-1] == ("dryrun", 3, "b")
    assert json.loads((Paths("dry7", "dryrun").results / "arm-result.json").read_text()) == {"stopped_at": 3,
                                                                                               "by": "stepflow"}
    assert ("bundle", "dryrun") in fake_orch.calls


def test_a_stopped_arm_leaves_the_others_running(fake_orch):
    fake_orch.outcome[("openspec", 3, "b")] = ["stopped"]
    real(fake_orch)
    assert not [x for x in fake_orch.runs() if x[0] == "openspec" and x[1] > 3]
    assert ("control", 7, "b") in fake_orch.runs()


# ---- per-step secret scan (review S-2) --------------------------------------------------------------------------

def test_a_secret_in_a_steps_evidence_stops_everything_until_scrubbed_and_is_never_rerun(fake_orch):
    fake_orch.findings[("dryrun", 2)] = 1
    with pytest.raises(orchestrate.NotReady, match="secret"):
        dry(fake_orch)
    assert [(e["kind"], e["signature"], e["arm"]) for e in faults.entries("dry7")] == \
        [("secret-in-evidence", "github-pat", "dryrun")]
    assert ("run_step", "dryrun", 2, "b") not in fake_orch.calls
    dry(fake_orch)
    assert count(fake_orch, ("run_step", "dryrun", 2, "a")) == 1


def test_every_run_is_scanned(fake_orch):
    dry(fake_orch)
    assert count(fake_orch, ("scan", "dryrun", 4)) == 2               # after 4.a and after 4.b


# ---- the owner's step review -------------------------------------------------------------------------------------

def test_a_pause_at_the_review_stops_cleanly_and_the_next_run_resumes(fake_orch):
    state = {"paused": False}

    def review(md):
        if "Step 2 " in md and not state["paused"]:
            state["paused"] = True
            return "pause", 0.0
        return "continue", 0.0
    fake_orch.owner.review_answer = review
    assert dry(fake_orch) == {"paused_after": 2}
    dry(fake_orch)
    assert fake_orch.runs() == [("dryrun", n, r) for n in range(1, 8) for r in ("a", "b")]


def test_a_parked_review_is_asked_again_before_the_arm_advances(fake_orch):
    answers = iter([PARK])
    fake_orch.owner.review_answer = lambda md: next(answers, ("continue", 0.0)) if "Step 2 " in md else ("continue", 0.0)
    assert "parked" in dry(fake_orch)
    assert ("run_step", "dryrun", 3, "a") not in fake_orch.calls
    dry(fake_orch)
    assert len([m for m in fake_orch.owner.reviews if "Step 2 " in m]) == 2
    assert count(fake_orch, ("run_step", "dryrun", 2, "b")) == 1


# ---- the end of an arm ----------------------------------------------------------------------------------------

def test_the_end_bundles_records_completion_and_publishes_to_the_private_repo_on_confirmation(fake_orch):
    real(fake_orch)
    for a in ARMS:
        assert ("bundle", a) in fake_orch.calls and ("publish", a) in fake_orch.calls
        assert json.loads((Paths("pass1", a).results / "arm-result.json").read_text())["completed"] is True


def test_a_parked_publish_confirmation_is_never_a_yes_and_is_retried_alone(fake_orch):
    fake_orch.owner.confirm_answer = lambda text: PARK if text.startswith("Push") else True
    r = real(fake_orch)
    assert progress("pass1", "openspec")["finished"]["published"] is None and r["parked"]
    fake_orch.owner.confirm_answer = lambda text: True
    fake_orch.calls.clear()
    real(fake_orch)
    assert fake_orch.runs() == [] and ("publish", "openspec") in fake_orch.calls
    assert progress("pass1", "openspec")["finished"]["published"] is True


def test_a_dry_arm_has_no_repo_to_publish(fake_orch):
    assert dry(fake_orch) == {"completed": True}
    assert ("publish", "dryrun") not in fake_orch.calls


def test_the_canary_stops_after_step_2(fake_orch):
    fake_orch.make("control", pass_="canary")
    r = orchestrate.run_arm("canary", "control", fake_orch.cred, fake_orch.owner, stop_after=2)
    assert r == {"stopped_after": 2} and max(x[1] for x in fake_orch.runs()) == 2
    assert ("bundle", "control") not in fake_orch.calls


# ---- refusals ------------------------------------------------------------------------------------------------

def test_nothing_runs_while_halted(fake_orch):
    faults.record(faults.HarnessFault("x", "y"), "dry7", "dryrun", 1, 1)
    faults.record(faults.HarnessFault("x", "y"), "dry7", "dryrun", 1, 1)
    with pytest.raises(orchestrate.NotReady, match="halted"):
        dry(fake_orch)
    assert fake_orch.runs() == []


def test_nothing_runs_unless_the_setup_is_clean_and_green(fake_orch, monkeypatch):
    def no(p):
        raise checklist.NotReady("setup checklist is not green")
    monkeypatch.setattr(checklist, "require_clean_green", no)
    with pytest.raises(orchestrate.NotReady, match="checklist"):
        dry(fake_orch)
    assert fake_orch.runs() == []


def test_nothing_runs_on_images_other_than_the_locked_ones(fake_orch, monkeypatch):
    from runner import preflight

    def no(arm, p):
        raise checklist.NotReady("image differs")
    monkeypatch.setattr(preflight, "check_images", no)
    with pytest.raises(orchestrate.NotReady, match="image"):
        dry(fake_orch)


def test_setup_drift_before_a_run_is_a_harness_fault(fake_orch, monkeypatch):
    monkeypatch.setattr(checklist, "verify", lambda p, arm, mode: [checklist.Check("common.claude-md", False, "gone")])
    with pytest.raises(orchestrate.NotReady, match="setup-drift"):
        dry(fake_orch)
    assert [(e["kind"], e["signature"]) for e in faults.entries("dry7")] == [("setup-drift", "common.claude-md")]


def test_limits_can_be_overridden_for_dry_arms_only(fake_orch):
    dry(fake_orch, limits_override={"turn_seconds": 20})
    assert fake_orch.ctxs[("dryrun", 1, "a")].pins.limits.turn_seconds == 20
    fake_orch.make("control", pass_="canary")
    with pytest.raises(PermissionError):
        orchestrate.run_arm("canary", "control", fake_orch.cred, fake_orch.owner, limits_override={"turn_seconds": 1})


def test_one_arm_alone_never_runs_on_the_real_pass(fake_orch):
    fake_orch.make("openspec", pass_="pass1")
    with pytest.raises(orchestrate.NotReady, match="run-pass"):
        orchestrate.run_arm("pass1", "openspec", fake_orch.cred, fake_orch.owner)


def test_run_pass_needs_the_recorded_order(fake_orch):
    with pytest.raises(orchestrate.NotReady, match="order"):
        orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)


def test_run_pass_sets_up_an_arm_that_has_no_state_once_the_owner_confirms(fake_orch):
    f = paths.RESULTS / "pass1" / "order.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"seed": 1, "rule": "t", "order": ["control"]}))
    fake_orch.owner.confirm_answer = lambda text: PARK if text.startswith("Set up") else True
    assert "parked" in orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    assert ("setup", "control") not in fake_orch.calls
    fake_orch.owner.confirm_answer = lambda text: True
    orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    assert ("setup", "control") in fake_orch.calls and ("control", 7, "b") in fake_orch.runs()


# ---- declared faults: re-run a step, re-test a commit --------------------------------------------------------------

def test_a_declared_rerun_supersedes_the_step_and_every_later_one_and_runs_them_again(fake_orch):
    dry(fake_orch)
    assert cli.main(["faults", "declare", "dry7", "dryrun", "3", "wrong-brief", "--scope", "rerun-step"]) == 0
    fake_orch.calls.clear()
    assert dry(fake_orch) == {"completed": True}
    p = Paths("dry7", "dryrun")
    assert fake_orch.runs() == [("dryrun", n, r) for n in range(3, 8) for r in ("a", "b")]
    assert fake_orch.calls.index(("restore", "dryrun", 3)) < fake_orch.calls.index(("run_step", "dryrun", 3, "a"))
    assert ("snapshot", "dryrun", 3) not in fake_orch.calls and ("snapshot", "dryrun", 4) in fake_orch.calls
    assert all((p.results / f"{n:02d}-superseded-1").is_dir() for n in range(3, 8))
    assert progress("dry7", "dryrun")["rerun"] is None


def test_a_declared_rerun_of_step2_keeps_the_hand_edit(fake_orch):
    dry(fake_orch)
    (Paths("dry7", "dryrun").step(2) / "hand-edit" / "edit.json").write_text("{}")
    assert cli.main(["faults", "declare", "dry7", "dryrun", "2", "wrong-brief", "--scope", "rerun-step"]) == 0
    fake_orch.calls.clear()
    dry(fake_orch)
    assert ("hand_edit", "dryrun", 2) not in fake_orch.calls
    assert (Paths("dry7", "dryrun").step(2) / "hand-edit" / "edit.json").exists()
    assert fake_orch.ctxs[("dryrun", 2, "b")].sha_before == "edit-sha"


def test_a_declared_retest_re_tests_the_recorded_commit_without_a_new_session(fake_orch):
    dry(fake_orch)
    p = Paths("dry7", "dryrun")
    (p.step(2) / "git.json").write_text(json.dumps({"sha_after": "sha-2"}))
    assert cli.main(["faults", "declare", "dry7", "dryrun", "2", "flaky-fixture", "--scope", "retest"]) == 0
    fake_orch.calls.clear()
    dry(fake_orch)
    assert fake_orch.runs() == []
    assert ("prepare", "dryrun", "02-retest1", "sha-2") in fake_orch.calls and ("quality", "dryrun") in fake_orch.calls
    assert (p.step(2) / "hidden-superseded-1" / "summary.json").exists()
    assert json.loads((p.step(2) / "retest-1.json").read_text())["sha"] == "sha-2"
    fake_orch.calls.clear()
    dry(fake_orch)                                                      # the declaration is honoured once
    assert not [c for c in fake_orch.calls if c[0] == "prepare"]


# ---- setup once per arm; moving state aside after a fault ------------------------------------------------------------

def test_setup_runs_once_and_again_only_moves_unstarted_state_aside(fake_orch):
    orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    with pytest.raises(orchestrate.NotReady, match="once"):
        orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner, again=True)
    assert [x.name for x in (paths.STATE / "dry7").iterdir() if ".aside-" in x.name]
    assert count(fake_orch, ("setup", "dryrun")) == 2


def test_setup_again_is_refused_once_a_step_has_started(fake_orch):
    dry(fake_orch)
    with pytest.raises(orchestrate.NotReady, match="started"):
        orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner, again=True)


def test_a_harness_fault_in_setup_is_recorded(fake_orch, monkeypatch):
    def boom(pass_, arm, cred, owner):
        raise faults.HarnessFault("model-pin", "claude-haiku-4-5", "setup")
    monkeypatch.setattr(checklist, "run_setup", boom)
    with pytest.raises(orchestrate.NotReady, match="model-pin"):
        orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    assert [(e["kind"], e["step"]) for e in faults.entries("dry7")] == [("model-pin", 0)]


# ---- close-out and status ------------------------------------------------------------------------------------

def test_close_out_needs_every_arm_finished(fake_orch):
    fake_orch.outcome[("openspec", 1, "a")] = ["parked"]
    real(fake_orch)
    with pytest.raises(orchestrate.NotReady, match="openspec"):
        orchestrate.close_out("pass1", fake_orch.owner)


def test_close_out_scans_checks_bundles_and_asks_for_every_pat_revocation(fake_orch, monkeypatch):
    real(fake_orch)
    for a in ARMS:
        (Paths("pass1", a).results / "repo.bundle").write_bytes(b"# v2 git bundle\n")
    from runner import secrets
    monkeypatch.setattr(secrets, "scan_tree", lambda root, lits=(): [])
    f = orchestrate.close_out("pass1", fake_orch.owner)
    text = f.read_text()
    assert "secret scan: clean" in text and "bundles: all present" in text
    ids = [i for i, _ in fake_orch.owner.item_calls[-1]]
    assert ids == ["pat-openspec", "pat-control", "pat-disc-openspec", "pat-disc-control"]      # A3: + discovery
    assert "- [x] pat-openspec" in text


def test_status_shows_every_arm_and_both_runs_of_each_step(fake_orch):
    fake_orch.outcome[("openspec", 2, "a")] = ["parked"]
    real(fake_orch)
    s = orchestrate.status()
    assert "pass1" in s and "openspec" in s and "control" in s
    assert "2:a=parked" in s and "1:a=discovered,b=done" in s


# ---- final fix batch A1: a run parked or crashed in its tests phase resumes at the tests, never restored ------------

@pytest.mark.parametrize("behaviour", ["tests-parked", "tests-paused-park", "tests-halt", "tests-boom"])
def test_a_run_stopped_in_its_tests_phase_is_resumed_without_a_restore(fake_orch, behaviour):
    fake_orch.outcome[("dryrun", 3, "b")] = [behaviour]
    try:
        dry(fake_orch)
    except (stepflow.Halt, RuntimeError):
        pass
    assert (Paths("dry7", "dryrun").step(3) / stepflow.PENDING).is_file()
    fake_orch.calls.clear()
    if behaviour == "tests-halt":
        faults.halt("dry7", "test", {}); faults.resume("dry7", "fixed")
    dry(fake_orch)
    c = fake_orch.calls
    assert ("run_step", "dryrun", 3, "b") in c and ("restore", "dryrun", 3) not in c
    assert not (Paths("dry7", "dryrun").step(3) / "b-interrupted-1").exists()     # the attempt's evidence stays


def test_a_tracker_fault_after_a_run_is_recorded_in_the_ledger_and_a_repeat_halts(fake_orch, monkeypatch):
    from runner import tracker

    def broken(ctx):
        raise faults.HarnessFault("infra-tracker", "list", "exit 1: HTTP 502")
    monkeypatch.setattr(tracker, "snapshot", broken)
    with pytest.raises(orchestrate.NotReady, match="infra-tracker"):
        dry(fake_orch)
    [e] = faults.entries("dry7")
    assert (e["kind"], e["signature"], e["step"], e["run"]) == ("infra-tracker", "list", 1, "b")
    with pytest.raises(stepflow.Halt):
        dry(fake_orch)


def test_a_container_error_in_the_step6_precheck_is_recorded_in_the_ledger(fake_orch, monkeypatch):
    from runner import hidden
    real_prepare = hidden.prepare

    def prepare(p, sha, label, out_dir, **k):
        if label == "06-precheck":
            raise stepflow.docker.ContainerError("export failed in container (1): boom")
        return real_prepare(p, sha, label, out_dir, **k)
    monkeypatch.setattr(hidden, "prepare", prepare)
    with pytest.raises(orchestrate.NotReady, match="infra-hidden"):
        dry(fake_orch)
    [e] = faults.entries("dry7")
    assert (e["kind"], e["step"]) == ("infra-hidden", 6)


def test_a_tracker_fault_filing_the_step6_issue_is_recorded_in_the_ledger(fake_orch, monkeypatch):
    from runner import tracker

    def broken(ctx, owner, *, title=None, body=None):
        raise faults.HarnessFault("infra-tracker", "create", "exit 1")
    monkeypatch.setattr(tracker, "create_bug", broken)
    with pytest.raises(orchestrate.NotReady, match="infra-tracker"):
        dry(fake_orch)
    [e] = faults.entries("dry7")
    assert (e["kind"], e["signature"], e["step"]) == ("infra-tracker", "create", 6)


# ---- final fix batch A3: N.a's discovery tracker ----------------------------------------------------------------------

def test_a_github_arms_6a_gets_its_bug_in_the_discovery_repo_and_6b_the_normal_one(fake_orch):
    real(fake_orch)
    runs = [(a, run) for a, n, run, _ in fake_orch.bug_runs if n == 6]
    assert sorted(runs) == sorted([(a, r) for a in ARMS for r in ("a", "b")])
    num = {(a, run): k for a, n, run, k in fake_orch.bug_runs if n == 6}
    for a in ARMS:
        assert f"troupe-run/x#{num[(a, 'a')]}." in fake_orch.firsts[(a, 6, "a")]
        assert f"troupe-run/x#{num[(a, 'b')]}." in fake_orch.firsts[(a, 6, "b")]
    assert fake_orch.ctxs[("openspec", 6, "a")].run == "a" and fake_orch.ctxs[("openspec", 6, "b")].run == "b"


def test_a_dry_arms_6a_and_6b_share_the_one_issue(fake_orch):
    dry(fake_orch)
    assert [(n, run) for _, n, run, _ in fake_orch.bug_runs] == [(6, "b")]


def test_a_declared_rerun_of_an_earlier_step_closes_the_stale_step6_issue(fake_orch):
    dry(fake_orch)
    assert cli.main(["faults", "declare", "dry7", "dryrun", "3", "wrong-brief", "--scope", "rerun-step"]) == 0
    fake_orch.calls.clear()
    dry(fake_orch)
    c = fake_orch.calls
    assert ("supersede", "dryrun", "troupe-run/x#1") in c
    assert c.index(("supersede", "dryrun", "troupe-run/x#1")) < c.index(("create_bug", "dryrun", None))
    assert progress("dry7", "dryrun").get("stale_issues") == []


def test_a_parked_close_of_a_stale_issue_is_retried_on_the_next_run(fake_orch):
    dry(fake_orch)
    assert cli.main(["faults", "declare", "dry7", "dryrun", "3", "wrong-brief", "--scope", "rerun-step"]) == 0
    fake_orch.owner.confirm_answer = lambda text: PARK if text.startswith("Close") else True
    r = dry(fake_orch)
    assert "parked" in r and progress("dry7", "dryrun")["stale_issues"]
    fake_orch.owner.confirm_answer = lambda text: True
    fake_orch.calls.clear()
    dry(fake_orch)
    assert ("supersede", "dryrun", "troupe-run/x#1") in fake_orch.calls


# ---- final fix batch A4 / m-3: the substitute is scored; an unscoreable precheck parks ---------------------------------

def test_a_substitute_arms_6b_carries_the_acceptance_test_and_the_precheck_baseline(fake_orch):
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("substitute", "Sub title", "Sub body", "why", "def test_x(): 0", 1.0)]
    fake_orch.acceptance = [{"outcome": "failed", "tests": {"m::x": "failed"}}]
    dry(fake_orch)
    acc = fake_orch.ctxs[("dryrun", 6, "b")].acceptance
    assert acc["body"] == "def test_x(): 0" and acc["baseline"] == {"m::new": "passed", "m::old": "passed"}
    assert fake_orch.ctxs[("dryrun", 6, "a")].acceptance is None                       # N.a is never scored
    p = Paths("dry7", "dryrun")
    assert not [f for d in (p.home, p.work) if d.exists() for f in d.rglob("*") if f.is_file()
                and "def test_x(): 0" in f.read_text(errors="replace")]           # never where the arm can read it


def test_no_acceptance_test_without_a_substitute(fake_orch):
    dry(fake_orch)
    assert fake_orch.ctxs[("dryrun", 6, "b")].acceptance is None


def test_an_unscoreable_precheck_parks_for_the_owner_instead_of_delivering_the_planted_bug(fake_orch, monkeypatch):
    from runner import hidden
    real_run = hidden.run
    monkeypatch.setattr(hidden, "run", lambda p, copy, step, out, install_failed=False, **k: hidden.summarise(
        6, {}, ["m::new"], [], [], -1, collected=["m::new"], attribution="harness-fault: pytest exit 2")
        if out.name == "precheck" else real_run(p, copy, step, out, install_failed, **k))
    r = dry(fake_orch)
    assert r["parked"][0]["what"] == "precheck-unscoreable"
    assert not [c for c in fake_orch.calls if c[0] == "create_bug"]
    assert (progress("dry7", "dryrun")["steps"].get("6") or {}).get("precheck") is None   # checked again next time
    monkeypatch.setattr(hidden, "run", real_run)
    fake_orch.calls.clear()
    dry(fake_orch)
    assert ("create_bug", "dryrun", None) in fake_orch.calls


def test_a_substitute_is_refused_when_the_step5_commit_does_not_install(fake_orch, monkeypatch):
    from runner import hidden
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("substitute", "A", "a", "w", "t1", 1.0), ("planted", "", "", "", "", 0.0)]
    real_prepare = hidden.prepare
    monkeypatch.setattr(hidden, "prepare", lambda p, sha, label, out, **k: hidden.Prepared(out, None, {"hidden": {"ok": False}})
                        if label == "06-substitute" else real_prepare(p, sha, label, out, **k))
    dry(fake_orch)
    assert ("create_bug", "dryrun", "A") not in fake_orch.calls and ("create_bug", "dryrun", None) in fake_orch.calls
    assert "does not install" in fake_orch.owner.substitutes[1]
    assert not [c for c in fake_orch.calls if c[0] == "acceptance"]


def test_a_precheck_of_an_arm_with_no_main_delivers_the_planted_bug(fake_orch, monkeypatch):
    from runner import hidden
    real_prepare = hidden.prepare

    def prepare(p, sha, label, out_dir, **k):
        if label == "06-precheck":
            raise hidden.NoMain("no main")
        return real_prepare(p, sha, label, out_dir, **k)
    monkeypatch.setattr(hidden, "prepare", prepare)
    dry(fake_orch)
    pc = json.loads((Paths("dry7", "dryrun").step(6) / "precheck" / "precheck.json").read_text())
    assert pc["planted_already_passes"] is False and pc["attribution"] == hidden.NO_MAIN
    assert ("create_bug", "dryrun", None) in fake_orch.calls


# ---- final fix batch A5: arm drift and the arm's own token are arm violations here too --------------------------------

def _viol(p):
    f = p.results / "arm-violations.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def test_arm_drift_found_before_a_run_is_an_arm_violation_repaired_by_the_steps_restore(fake_orch):
    calls = {"n": 0}
    from runner import checklist
    from runner.checklist import Check

    def verify(p, arm, mode):
        calls["n"] += 1
        return [Check("common.origin", False, "origin changed")] if calls["n"] == 3 else []
    import pytest as _p
    mp = _p.MonkeyPatch(); mp.setattr(checklist, "verify", verify)
    try:
        assert dry(fake_orch) == {"completed": True}
    finally:
        mp.undo()
    p = Paths("dry7", "dryrun")
    [v] = _viol(p)
    assert (v["kind"], v["check"]) == ("setup-drift", "common.origin") and faults.entries("dry7") == []
    assert ("restore", "dryrun", 2) in fake_orch.calls


def test_non_arm_drift_before_a_run_is_still_a_harness_fault(fake_orch):
    fake_orch.verify_now = ["common.clean-green"]
    with pytest.raises(orchestrate.NotReady, match="setup-drift"):
        dry(fake_orch)
    assert faults.entries("dry7")[0]["kind"] == "setup-drift"


def test_arm_drift_that_a_restore_cannot_repair_stops_for_the_owner_without_the_ledger(fake_orch):
    fake_orch.verify_now = ["common.git-identity"]
    with pytest.raises(orchestrate.NotReady, match="arm"):
        dry(fake_orch)
    assert faults.entries("dry7") == [] and _viol(Paths("dry7", "dryrun"))


def test_the_arms_own_token_found_by_the_step_scan_is_redacted_not_a_fault(fake_orch, monkeypatch):
    from runner import secrets
    own = "github_pat_" + "Q" * 60
    fake_orch.own = [own]

    def run_step(ctx, first, extra=None, run="b"):
        (ctx.out).mkdir(parents=True, exist_ok=True)
        (ctx.out / "egress.log").write_text(f"CONNECT api.github.com {own}\n")
        return real_run_step(ctx, first, extra, run)
    from runner import stepflow as sf
    real_run_step = sf.run_step
    monkeypatch.setattr(sf, "run_step", run_step)
    monkeypatch.setattr(secrets, "scan_step", lambda p, n, lits=(): secrets.scan_tree(p.step(n), [own]))
    assert dry(fake_orch) == {"completed": True}
    assert faults.entries("dry7") == []
    p = Paths("dry7", "dryrun")
    assert own not in (p.step(3) / "egress.log").read_text()
    assert [v["kind"] for v in _viol(p)][:1] == ["own-token-in-evidence"]


# ---- m-7: setup evidence is secret-scanned at the end of setup -------------------------------------------------------

def test_setup_evidence_is_scanned_when_setup_ends(fake_orch, monkeypatch):
    from runner import checklist, secrets
    def run_setup(pass_, arm, cred, owner):
        p = Paths(pass_, arm); p.base.mkdir(parents=True)
        p.setup_results.mkdir(parents=True, exist_ok=True)
        (p.setup_results / "shell-history.txt").write_text("echo dry-run-dummy-token\n")
        return checklist.SetupResult([], {}, True, 0.0)
    monkeypatch.setattr(checklist, "run_setup", run_setup)
    (paths.STATE / "dry7").mkdir(parents=True, exist_ok=True)
    with pytest.raises(orchestrate.NotReady, match="secret-in-evidence"):
        orchestrate.setup("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    [e] = faults.entries("dry7")
    assert (e["kind"], e["step"]) == ("secret-in-evidence", 0)
    rec = json.loads((Paths("dry7", "dryrun").setup_results / "secret-scan.json").read_text())
    assert rec["clean"] is False and "shell-history.txt" in rec["findings"][0]


def test_a_run_refuses_an_arm_whose_setup_scan_found_a_secret_until_it_is_clean(fake_orch):
    fake_orch.make("dryrun", pass_="dry7")
    p = Paths("dry7", "dryrun")
    p.setup_results.mkdir(parents=True, exist_ok=True)
    (p.setup_results / "leak.txt").write_text("dry-run-dummy-token")
    with pytest.raises(orchestrate.NotReady, match="secret"):
        orchestrate.run_arm("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    (p.setup_results / "leak.txt").write_text("scrubbed")
    assert orchestrate.run_arm("dry7", "dryrun", fake_orch.cred, fake_orch.owner) == {"completed": True}
    assert json.loads((p.setup_results / "secret-scan.json").read_text())["clean"] is True


# ---- m-8: the canary gets its own copy of the PO brief when it starts ------------------------------------------------

def test_the_canary_start_copies_the_po_brief_once_and_never_overwrites_it(tmp_state, monkeypatch):
    monkeypatch.setattr(orchestrate, "_run", lambda pass_, arms, cred, owner, **k: {"arms": {a: {} for a in arms}})
    monkeypatch.setattr(orchestrate, "_single", lambda res, arm: res)
    b = paths.STATE / "canary" / "po-brief.md"
    orchestrate.run_arm("canary", "control", None, None, stop_after=1)
    assert b.read_text() == (paths.REPO_ROOT / "scenario" / "po-brief.md").read_text()
    b.write_text(b.read_text() + "\n- **Q:** grown **A:** kept\n")
    orchestrate.run_arm("canary", "control", None, None, stop_after=1)
    assert "grown" in b.read_text()


# ---- m-9: the consistency check is crash-safe: the brief edit is committed before the check is recorded -------------

def _conflict_then_edit(env):
    env.escalate[("openspec", 1)] = (Q, "Yes.")
    env.escalate[("control", 1)] = (Q, "No.")
    answers = iter([False, True, True])
    env.owner.items_answer = lambda items: {i: (next(answers, True), "", 0.0) for i, _ in items}

    def edit(text):
        if "Edit" in text:
            env.brief.write_text(env.brief.read_text().replace("**A:** No.", "**A:** Yes."))
        return True
    env.owner.confirm_answer = edit


def test_the_brief_edit_is_committed_before_the_check_is_recorded_as_confirmed(fake_orch, monkeypatch):
    from runner import gitops
    _conflict_then_edit(fake_orch)
    f = paths.RESULTS / "pass1" / "consistency" / "step-01.json"
    at_commit = []
    monkeypatch.setattr(gitops, "commit_harness_file",
                        lambda path, msg: at_commit.append((json.loads(f.read_text()) if f.exists() else {}).get("status")))
    real(fake_orch)
    assert at_commit and at_commit[0] != "confirmed"
    assert json.loads(f.read_text())["committed"] is True


def test_a_crash_while_committing_the_edit_leaves_the_check_unconfirmed_so_it_runs_again(fake_orch, monkeypatch):
    from runner import gitops
    _conflict_then_edit(fake_orch)
    calls = []

    def commit(path, msg):
        calls.append(msg)
        if len(calls) == 1:
            raise KeyboardInterrupt("killed while committing")
    monkeypatch.setattr(gitops, "commit_harness_file", commit)
    with pytest.raises(KeyboardInterrupt):
        real(fake_orch)
    f = paths.RESULTS / "pass1" / "consistency" / "step-01.json"
    assert json.loads(f.read_text())["status"] != "confirmed"
    real(fake_orch)
    assert len(calls) == 2 and json.loads(f.read_text())["status"] == "confirmed"


def test_the_oauth_token_left_in_hosts_yml_and_printed_is_still_a_harness_fault(fake_orch, monkeypatch):   # follow-up 2
    from runner import credentials, secrets
    oauth = "gho_" + "O" * 40
    cred = credentials.Credential(oauth)
    monkeypatch.setattr(secrets, "own_pat_values", REAL_OWN)
    monkeypatch.setattr(secrets, "scan_step", lambda p, n, lits=(): secrets.scan_tree(p.step(n), [oauth]))
    fake_orch.make("dryrun", pass_="dry7")
    p = Paths("dry7", "dryrun")
    (p.home / ".config" / "gh").mkdir(parents=True)
    (p.home / ".config" / "gh" / "hosts.yml").write_text(f"github.com:\n    oauth_token: {oauth}\n")
    p.step(1).mkdir(parents=True)
    (p.step(1) / "egress.log").write_text(f"leaked {oauth}\n")
    with pytest.raises(orchestrate.NotReady, match="secret-in-evidence"):
        orchestrate.run_arm("dry7", "dryrun", cred, fake_orch.owner)
    assert oauth in (p.step(1) / "egress.log").read_text()                 # never redacted as the arm's own
    assert faults.entries("dry7")[0]["kind"] == "secret-in-evidence"


def test_a_crash_after_the_brief_commit_resumes_without_committing_it_again(fake_orch, monkeypatch):   # follow-up 5
    from runner import gitops
    _conflict_then_edit(fake_orch)
    head = {"text": fake_orch.brief.read_text()}
    commits = []

    def commit(path, msg):
        commits.append(msg)
        head["text"] = path.read_text()                  # committed: HEAD now has the edit
        if len(commits) == 1:
            raise KeyboardInterrupt("killed right after the commit")
    monkeypatch.setattr(gitops, "commit_harness_file", commit)
    monkeypatch.setattr(gitops, "harness_differs_from_head", lambda path: path.read_text() != head["text"])
    with pytest.raises(KeyboardInterrupt):
        real(fake_orch)
    real(fake_orch)
    f = paths.RESULTS / "pass1" / "consistency" / "step-01.json"
    rec = json.loads(f.read_text())
    assert len(commits) == 1 and rec["status"] == "confirmed" and rec["edited"] is True


def test_the_check_never_commits_a_brief_identical_to_head(fake_orch, monkeypatch):
    from runner import gitops
    _conflict_then_edit(fake_orch)
    commits = []
    monkeypatch.setattr(gitops, "commit_harness_file", lambda path, msg: commits.append(msg))
    monkeypatch.setattr(gitops, "harness_differs_from_head", lambda path: False)
    real(fake_orch)
    assert commits == []


def test_arm_drift_checks_are_skipped_when_the_tests_phase_resumes(fake_orch, monkeypatch):   # follow-up 7
    from runner import checklist
    from runner.checklist import Check
    fake_orch.outcome[("dryrun", 3, "b")] = ["tests-parked"]
    dry(fake_orch)
    fake_orch.calls.clear()
    pending = Paths("dry7", "dryrun").step(3) / stepflow.PENDING
    # stepflow already judged this attempt's drift (its pending record); the check still reports it meanwhile
    monkeypatch.setattr(checklist, "verify", lambda p, arm, mode: [Check("common.origin", False, "x")]
                        if pending.exists() else [])
    dry(fake_orch)
    assert ("run_step", "dryrun", 3, "b") in fake_orch.calls and ("restore", "dryrun", 3) not in fake_orch.calls
    assert _viol(Paths("dry7", "dryrun")) == []


def test_resource_exhaustion_in_na_never_counts_towards_the_suite_halt_or_the_reruns(fake_orch):   # follow-up 8
    faults.record_resource("pass1", "control", 3, 1, "repeat", [["session-oom"]], run="a")
    fake_orch.resource[("openspec", 3)] = "repeat"
    real(fake_orch)
    assert not faults.halted("pass1")


def test_a_substitute_whose_acceptance_run_died_is_refused_and_says_so(fake_orch):        # round 2, item 5
    fake_orch.precheck_passes = True
    fake_orch.owner.substitute_answers = [("substitute", "A", "a", "w", "t1", 1.0), ("planted", "", "", "", "", 0.0)]
    fake_orch.acceptance = [{"outcome": "failed", "attribution": "arm-resource",
                             "resource_evidence": [["oom-kill:1"], ["oom-kill:1"]]}]
    dry(fake_orch)
    assert ("create_bug", "dryrun", "A") not in fake_orch.calls and ("create_bug", "dryrun", None) in fake_orch.calls
    msg = fake_orch.owner.substitutes[1]
    assert "died (arm-resource)" in msg and "did not fail" not in msg


# ---- round 2, item 9: the consistency record says what really happened to the brief edit ------------------------------

def test_a_dry_pass_records_its_brief_edit_as_not_committed(fake_orch):
    fake_orch.make("dryrun", pass_="dry7")
    _conflict_then_edit(fake_orch)                       # the owner's edit on the "Edit …" prompt
    fake_orch.escalate = {("dryrun", 1): (Q, "No.")}
    answers = iter([False, True])
    fake_orch.owner.items_answer = lambda items: {i: (next(answers, True), "", 0.0) for i, _ in items}
    orchestrate.run_arm("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    rec = json.loads((paths.RESULTS / "dry7" / "consistency" / "step-01.json").read_text())
    assert rec["edited"] is True and rec["committed"] is False and rec["committed_now"] is False


def test_a_real_pass_records_a_commit_made_now_and_one_made_before_a_crash(fake_orch, monkeypatch):
    from runner import gitops
    _conflict_then_edit(fake_orch)
    head = {"text": fake_orch.brief.read_text()}
    commits = []

    def commit(path, msg):
        commits.append(msg); head["text"] = path.read_text()
        if len(commits) == 1:
            raise KeyboardInterrupt("killed right after the commit")
    monkeypatch.setattr(gitops, "commit_harness_file", commit)
    monkeypatch.setattr(gitops, "harness_differs_from_head", lambda path: path.read_text() != head["text"])
    with pytest.raises(KeyboardInterrupt):
        real(fake_orch)
    real(fake_orch)
    rec = json.loads((paths.RESULTS / "pass1" / "consistency" / "step-01.json").read_text())
    assert (rec["committed"], rec["committed_now"]) == (True, False)      # in HEAD, by the run that crashed
