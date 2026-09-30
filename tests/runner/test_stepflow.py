# Task 22: one step for one arm — attempts, the stop rule, harness faults, and the N.a / N.b runs
# (drive/hidden/quality/evidence faked by conftest.fake_step).
import json
import pytest
from runner import faults, owner, paths, stepflow
from runner.faults import HarnessFault


PARK = owner.Park("gate", "spec sign-off", "unattended", 0.0, 0.0)


# ---- the plan's tests (brief Step 1) ----------------------------------------------------------------------------

def test_three_no_progress_attempts_stop_the_arm(fake_step):
    fake_step.progress = [0, 0, 0]
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and out.attempts == 3
    assert fake_step.messages == ["go", fake_step.no_progress, fake_step.no_progress]


def test_partial_progress_is_final(fake_step):
    fake_step.progress = [2]
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "done" and out.attempts == 1


def test_harness_fault_restores_the_snapshot_and_does_not_count(fake_step):
    fake_step.raise_on = {1: ("model-pin", "claude-haiku-4-5")}
    fake_step.progress = [3]
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "done" and out.attempts == 1 and fake_step.restored == [fake_step.ctx.step]


def test_a_harness_fault_after_no_progress_resets_the_count_and_parks_both(fake_step):     # review C-3
    fake_step.progress = [0, 0, 0, 0]
    fake_step.raise_on = {2: ("infra-container", "boom")}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and out.attempts == 3                 # three arm attempts after the restore
    assert fake_step.messages == ["go", fake_step.no_progress, "go", fake_step.no_progress, fake_step.no_progress]
    assert (1, "harness-infra-container") in fake_step.parked and (2, "harness-infra-container") in fake_step.parked


def test_pin_violation_found_after_a_clean_attempt_is_still_a_harness_fault(fake_step):
    fake_step.pin_violation_on = {1: "claude-sonnet-5"}
    fake_step.progress = [3, 3]
    out = stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.restored == [fake_step.ctx.step] and out.status == "done"


def test_a_harness_flake_is_retested_on_the_same_commit(fake_step):
    fake_step.progress = [1]
    fake_step.harness_flaky_first = ["tests.hidden.test_step2_sync::test_x"]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.hidden_runs == 2 and fake_step.prepares == 1


def test_first_runaway_breach_may_be_reclassified_by_the_owner(fake_step):  # OD14 B
    fake_step.breach_on = {1: "exchanges"}
    fake_step.ctx.owner.reclassify = lambda what, detail: "harness"
    fake_step.progress = [2]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.restored == [fake_step.ctx.step]


# ---- binding rulings ------------------------------------------------------------------------------------------

def test_a_parked_attempt_returns_a_parked_step_without_scoring_or_counting_it(fake_step):   # ruling 1
    fake_step.outcome_on = {1: "parked"}
    fake_step.park_on = {1: PARK}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "parked" and out.attempts == 0 and out.park == PARK
    assert fake_step.hidden_runs == 0 and fake_step.finalised == [] and fake_step.restored == []
    assert faults.for_step("dry9", "control", 2) == []                   # not a fault either
    rec = json.loads((fake_step.ctx.out / "parked.json").read_text())
    assert rec["attempt"] == 1 and rec["park"]["reason"] == "unattended" and rec["run"] == "b"


def test_a_park_after_no_progress_attempts_reports_only_the_arm_attempts_before_it(fake_step):
    fake_step.progress = [0, 0]
    fake_step.outcome_on = {2: "parked"}
    fake_step.park_on = {2: PARK}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "parked" and out.attempts == 1


def test_a_harness_restore_resets_the_later_messages_so_cr_b_is_sent_again(fake_step):     # ruling 2
    fake_step.raise_on = {2: ("infra-container", "boom")}
    fake_step.progress = [0, 0, 3]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.later_sent_at_call == [0, 1, 0]


def test_the_later_messages_carry_over_between_no_progress_attempts(fake_step):
    fake_step.progress = [0, 3]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.later_sent_at_call == [0, 1]


def test_a_raised_fault_still_has_its_transcripts_pin_checked(fake_step):                   # ruling 3
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    assert len(fake_step.verify_calls) == 2                              # the faulted attempt and the clean one
    assert fake_step.verify_calls[0]["streams"] == [fake_step.ctx.out.parent / "arm-a1.stream.jsonl"]


def test_an_off_pin_model_behind_a_raised_fault_is_what_the_ledger_records(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.pin_violation_on = {1: "claude-haiku-4-5"}
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("model-pin", "claude-haiku-4-5") and "infra-container: boom" in e["detail"]


def test_an_auth_failure_keeps_precedence_over_a_pin_violation(fake_step):
    fake_step.raise_on = {1: ("infra-auth", "authentication_failed")}
    fake_step.pin_violation_on = {1: "claude-haiku-4-5"}
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-auth"


def test_verify_pin_gets_the_runner_streams_with_their_outcomes_and_the_skipped_entries(fake_step):   # ruling 4
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    [c] = fake_step.verify_calls
    stream = fake_step.ctx.out.parent / "arm-a1.stream.jsonl"
    assert c["streams"] == [stream] and c["stream_outcomes"] == {stream: "ok"} and c["unsafe"] == []


def test_an_unverified_stream_is_a_harness_fault(fake_step, monkeypatch):
    from runner.transcripts import PinReport
    reports = [PinReport(False, 1, 1, 0, 0, ["2.1.281"], False, [], ["s.jsonl"]),
               PinReport(True, 1, 1, 0, 0, ["2.1.281"], False, [])]
    monkeypatch.setattr(stepflow.transcripts, "verify_pin", lambda *a, **k: reports.pop(0))
    fake_step.progress = [3, 3]
    stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("model-pin", "unverified")


def test_a_repeated_resource_exhaustion_is_all_failed_and_recorded_not_a_harness_fault(fake_step):   # ruling 5
    fake_step.progress = [3, 3, 3]
    fake_step.attribution_on = {1: ("arm-resource", [["oom-kill:1"], ["oom-kill:1"]])}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert faults.for_step("dry9", "control", 2) == [] and fake_step.restored == []
    [r] = faults.resource_records("dry9", 2)
    assert (r["arm"], r["exhausted"], r["attempt"]) == ("control", "repeat", 1)
    assert out.attempts == 2                                             # all-failed: no progress at attempt 1


def test_a_resource_exhaustion_that_passed_on_its_rerun_is_recorded_as_once(fake_step):
    fake_step.progress = [3]
    fake_step.attribution_on = {1: (None, [["pids-max:3"], []])}
    stepflow.run_step(fake_step.ctx, "go")
    [r] = faults.resource_records("dry9", 2)
    assert r["exhausted"] == "once"


def test_an_output_overflow_is_the_arms_all_failed_result(fake_step):
    fake_step.progress = [3, 3]
    fake_step.attribution_on = {1: ("arm-output: /results full: junit.xml", [[]])}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.attempts == 2 and faults.for_step("dry9", "control", 2) == []


def test_a_hidden_harness_fault_is_an_infra_fault_retested_on_the_same_commit(fake_step):
    fake_step.progress = [3]
    fake_step.attribution_on = {1: ("harness-fault: pytest exit 137", [])}
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-hidden" and e["signature"] == "pytest exit"
    assert fake_step.hidden_runs == 2 and fake_step.prepares == 1 and fake_step.calls == 1
    assert out.status == "done" and out.hidden.scoreable


def test_the_teammate_turns_reach_the_evidence_as_extra_turns(fake_step):                  # ruling 7
    fake_step.progress = [3]
    turns = [object()]
    stepflow.run_step(fake_step.ctx, "go", extra={"teammate": turns})
    [k] = fake_step.finalised
    assert k["extra_turns"] == {"teammate": turns} and k["outcome"] == "done"


# ---- the stop rule's record -------------------------------------------------------------------------------------

def test_a_stopped_arm_writes_its_arm_result(fake_step):
    fake_step.progress = [0, 0, 0]
    stepflow.run_step(fake_step.ctx, "go")
    r = json.loads((paths.Paths("dry9", "control").results / "arm-result.json").read_text())
    assert r["stopped_at"] == 2 and r["reason"] == "no progress in 3 attempts"
    assert r["last_hidden"]["new_discriminating_passed"] == 0
    assert fake_step.finalised[-1]["outcome"] == "stopped" and fake_step.quality_runs == 1


def test_no_progress_attempts_are_parked_but_the_scored_one_is_not(fake_step):
    fake_step.progress = [0, 3]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.parked == [(1, "no-progress")]


def test_the_scored_evidence_carries_only_the_attempts_since_the_last_restore(fake_step):
    fake_step.progress = [0, 0, 3]
    fake_step.raise_on = {1: ("infra-container", "boom")}
    stepflow.run_step(fake_step.ctx, "go")
    assert len(fake_step.finalised[-1]["attempts"]) == 2


def test_a_resumed_tests_phase_keeps_the_later_messages_already_sent(fake_step):
    fake_step.progress = [0, 3]
    fake_step.ctx.later_messages = ["CR-B"]
    fake_step.attribution_on = {1: ("harness-fault: pytest exit 137", [])}
    answers = [PARK]
    fake_step.ctx.owner.confirm = lambda text: answers.pop(0) if answers else True
    stepflow.run_step(fake_step.ctx, "go")                              # attempt 1 sent CR-B, parked in its tests
    fake_step.ctx.later_sent = 0                                        # a new process: a fresh StepCtx
    fake_step.attribution_on = {}
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.later_sent_at_call == [0, 1]


# ---- the owner's side of a harness fault -----------------------------------------------------------------------

def test_a_second_identical_fault_halts(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom"), 2: ("infra-container", "boom")}
    with pytest.raises(stepflow.Halt):
        stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.restored == [2]                                    # the first re-ran; the second halted


def test_an_owner_who_declines_the_rerun_pauses_the_step(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.ctx.owner.confirm = lambda text: False
    with pytest.raises(stepflow.Paused):
        stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.restored == []


def test_an_owner_park_at_the_rerun_prompt_pauses_the_step(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.ctx.owner.confirm = lambda text: PARK
    with pytest.raises(stepflow.Paused) as e:
        stepflow.run_step(fake_step.ctx, "go")
    assert e.value.park == PARK and fake_step.restored == []


def test_an_owner_park_at_the_breach_prompt_parks_the_step(fake_step):
    fake_step.breach_on = {1: "exchanges"}
    fake_step.ctx.owner.reclassify = lambda what, detail: PARK
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "parked" and fake_step.hidden_runs == 0


def test_only_the_first_breach_per_arm_goes_to_the_owner(fake_step):
    asked = []
    fake_step.breach_on = {1: "exchanges", 2: "turn_seconds"}
    fake_step.ctx.owner.reclassify = lambda what, detail: asked.append(what) or "arm"
    fake_step.progress = [0, 3]
    stepflow.run_step(fake_step.ctx, "go")
    assert asked == ["exchanges"]


def test_a_restore_calls_on_restore_for_a_new_first_message(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.ctx.on_restore = lambda: "go again (new issue)"
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.messages == ["go", "go again (new issue)"]


def test_a_named_snapshot_is_what_a_harness_restore_uses(fake_step):
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.ctx.snapshot = "02-pre-edit"
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.restored == ["02-pre-edit"]


# ---- N.a: the discovery run ------------------------------------------------------------------------------------

def _run_a(fs):
    fs.ctx.out = fs.ctx.out / "a"
    fs.ctx.out.mkdir(parents=True, exist_ok=True)


def test_run_a_asks_drive_for_the_discovery_stop_and_restores_the_pre_step_snapshot(fake_step):     # L-6
    _run_a(fake_step)
    fake_step.outcome_on = {1: "discovery-stop"}
    out = stepflow.run_step(fake_step.ctx, "go", run="a")
    assert fake_step.run_attempt_kw == [{"stop_at_first_gate_or_code": True}]
    assert out.status == "discovered" and fake_step.restored == [2]


def test_run_a_runs_no_hidden_tests_no_quality_and_no_scoring(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "discovery-stop"}
    stepflow.run_step(fake_step.ctx, "go", run="a")
    assert (fake_step.hidden_runs, fake_step.prepares, fake_step.quality_runs, fake_step.finalised) == (0, 0, 0, [])


def test_run_a_keeps_its_evidence_under_a(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "discovery-stop"}
    stepflow.run_step(fake_step.ctx, "go", run="a")
    rec = json.loads((fake_step.ctx.out / "discovery.json").read_text())
    assert rec["run"] == "a" and rec["outcome"] == "discovery-stop" and rec["model_pin_ok"] is True
    assert (fake_step.ctx.out / "cost.json").exists()


def test_run_a_refuses_an_out_dir_that_is_not_the_steps_a_dir(fake_step):
    with pytest.raises(ValueError):
        stepflow.run_step(fake_step.ctx, "go", run="a")


def test_run_a_never_sends_a_second_attempt_even_when_the_arm_stalls(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "stalled"}
    out = stepflow.run_step(fake_step.ctx, "go", run="a")
    assert fake_step.calls == 1 and out.status == "discovered" and fake_step.restored == [2]


def test_run_a_harness_fault_is_recorded_restored_and_rerun(fake_step):
    _run_a(fake_step)
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.outcome_on = {2: "discovery-stop"}
    out = stepflow.run_step(fake_step.ctx, "go", run="a")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["run"] == "a" and fake_step.restored == [2, 2] and out.status == "discovered"
    assert fake_step.later_sent_at_call == [0, 0]


def test_run_a_parked_is_a_parked_step_left_for_the_owner(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "parked"}
    fake_step.park_on = {1: PARK}
    out = stepflow.run_step(fake_step.ctx, "go", run="a")
    assert out.status == "parked" and fake_step.restored == []


def test_run_b_drives_every_attempt_to_completion(fake_step):
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go", run="b")
    assert fake_step.run_attempt_kw == [{}]


def test_an_unknown_run_is_refused(fake_step):
    with pytest.raises(ValueError):
        stepflow.run_step(fake_step.ctx, "go", run="c")


# ---- park() on disk --------------------------------------------------------------------------------------------

def test_park_moves_a_harness_attempts_turns_transcripts_po_and_log_lines(tmp_path):
    out = tmp_path
    (out / "turns").mkdir(); (out / "turns" / "arm-a2-001.stream.jsonl").write_text("x")
    (out / "turns" / "arm-a3-001.stream.jsonl").write_text("y")
    (out / "transcripts" / "a2").mkdir(parents=True); (out / "transcripts" / "a2" / "t.jsonl.gz").write_text("z")
    (out / "po" / "a2-001").mkdir(parents=True)
    (out / "hidden").mkdir(); (out / "hidden" / "summary.json").write_text("{}")
    (out / "questions.jsonl").write_text(json.dumps({"attempt": 2}) + "\n" + json.dumps({"attempt": 3}) + "\n")
    stepflow.park(out, 2, "harness-model-pin")
    dest = out / "attempts" / "2-harness-model-pin"
    assert (dest / "turns" / "arm-a2-001.stream.jsonl").exists() and (out / "turns" / "arm-a3-001.stream.jsonl").exists()
    assert (dest / "transcripts" / "t.jsonl.gz").exists() and (dest / "po" / "a2-001").is_dir()
    assert (dest / "hidden" / "summary.json").exists() and not (out / "hidden").exists()
    assert [json.loads(l)["attempt"] for l in (out / "questions.jsonl").read_text().splitlines()] == [3]
    assert json.loads((dest / "questions.jsonl").read_text())["attempt"] == 2
    assert json.loads((dest / "attempt.json").read_text()) == {"attempt": 2, "label": "harness-model-pin"}


def test_park_of_a_no_progress_attempt_keeps_its_turns_and_questions_on_top(tmp_path):
    out = tmp_path
    (out / "turns").mkdir(); (out / "turns" / "arm-a1-001.stream.jsonl").write_text("x")
    (out / "hidden").mkdir(); (out / "hidden" / "summary.json").write_text("{}")
    (out / "questions.jsonl").write_text(json.dumps({"attempt": 1}) + "\n")
    stepflow.park(out, 1, "no-progress")
    assert (out / "turns" / "arm-a1-001.stream.jsonl").exists() and (out / "questions.jsonl").read_text()
    assert (out / "attempts" / "1-no-progress" / "hidden" / "summary.json").exists()


def test_park_folds_an_earlier_no_progress_record_into_the_harness_one(tmp_path):
    out = tmp_path
    (out / "hidden").mkdir(); (out / "hidden" / "summary.json").write_text("{}")
    stepflow.park(out, 1, "no-progress")
    stepflow.park(out, 1, "harness-infra-container")
    assert not (out / "attempts" / "1-no-progress").exists()
    assert (out / "attempts" / "1-harness-infra-container" / "no-progress" / "hidden" / "summary.json").exists()


# ---- the hand edit's harness faults -----------------------------------------------------------------------------

def test_a_failed_hand_edit_is_recorded_and_retried_keeping_every_teammates_turns(fake_step, monkeypatch):
    from runner.handedit import HandEdit
    calls = []

    def apply(ctx, step1):
        calls.append(step1)
        if len(calls) == 1:
            f = HarnessFault("hand-edit", "scope", "outside")
            f.hand_edit_turns = ["t1", "t2"]
            raise f
        return HandEdit("sha", [], [], {}, 1, {}, turns=["t3"])
    monkeypatch.setattr(stepflow.handedit, "apply", apply)
    edit = stepflow.hand_edit(fake_step.ctx, {"m::t": "passed"})
    assert edit.turns == ["t1", "t2", "t3"] and len(calls) == 2
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("hand-edit", "scope")


def test_a_hand_edit_failing_the_same_way_twice_halts(fake_step, monkeypatch):
    def apply(ctx, step1):
        f = HarnessFault("hand-edit", "probe", "x"); f.hand_edit_turns = []
        raise f
    monkeypatch.setattr(stepflow.handedit, "apply", apply)
    with pytest.raises(stepflow.Halt):
        stepflow.hand_edit(fake_step.ctx, {})


# ---- errors from the runner itself ------------------------------------------------------------------------------

def test_a_docker_error_raised_by_the_runner_is_an_infra_container_fault(fake_step, monkeypatch):
    real = stepflow.drive.run_attempt
    calls = []

    def boom_once(c, attempt, message, resume=None, **kw):
        calls.append(attempt)
        if len(calls) == 1:
            raise stepflow.docker.ContainerError("docker run failed (125): proxy container exited 42")
        return real(c, attempt, message, resume, **kw)
    monkeypatch.setattr(stepflow.drive, "run_attempt", boom_once)
    fake_step.progress = [3]
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("infra-container", "docker run failed (): proxy container exited")
    assert fake_step.restored == [2] and out.status == "done"


def test_a_setup_that_is_not_ready_is_refused_not_recorded_as_a_fault(fake_step, monkeypatch):
    def not_ready(*a, **k):
        raise stepflow.checklist.NotReady("setup is dirty")
    monkeypatch.setattr(stepflow.drive, "run_attempt", not_ready)
    with pytest.raises(stepflow.checklist.NotReady):
        stepflow.run_step(fake_step.ctx, "go")
    assert faults.for_step("dry9", "control", 2) == []


def test_run_a_never_asks_the_owner_about_a_breach(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "stalled"}
    fake_step.breach_on = {1: "exchanges"}
    fake_step.ctx.owner.reclassify = lambda what, detail: pytest.fail("asked in run a")
    stepflow.run_step(fake_step.ctx, "go", run="a")
    assert not (paths.Paths("dry9", "control").results / "breaches.json").exists()


# ---- fix round 1 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [NotImplementedError("todo"), RecursionError("deep"), RuntimeError("a runner bug"),
                                 PermissionError("the dummy credential may only drive dry-run arms")])
def test_a_runner_bug_propagates_and_is_not_recorded_as_a_harness_fault(fake_step, monkeypatch, exc):   # L-1
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(stepflow.drive, "run_attempt", boom)
    with pytest.raises(type(exc)):
        stepflow.run_step(fake_step.ctx, "go")
    assert faults.for_step("dry9", "control", 2) == [] and fake_step.restored == []


def test_a_subprocess_timeout_from_the_runner_is_an_infra_container_fault(fake_step, monkeypatch):
    import subprocess
    real, calls = stepflow.drive.run_attempt, []

    def once(c, attempt, message, resume=None, **kw):
        calls.append(attempt)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(["docker", "run"], 600)
        return real(c, attempt, message, resume, **kw)
    monkeypatch.setattr(stepflow.drive, "run_attempt", once)
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-container"


def test_a_failure_collecting_a_faulted_attempts_evidence_still_records_the_original_fault(fake_step, monkeypatch):  # L-2
    fake_step.raise_on = {1: ("infra-container", "boom")}
    fake_step.progress = [3]
    n = []

    def collect(d, b, dest, **k):
        n.append(1)
        if len(n) == 1:
            raise OSError("transcripts unreadable")
        return []
    monkeypatch.setattr(stepflow.transcripts, "collect", collect)
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("infra-container", "boom") and "transcripts unreadable" in e["detail"]
    assert fake_step.restored == [2] and out.status == "done"


def test_the_scored_evidence_lists_only_run_b_faults(fake_step):                                  # L-5
    faults.record(HarnessFault("infra-container", "in-a"), "dry9", "control", 2, 1, run="a")
    fake_step.raise_on = {1: ("infra-container", "in-b")}
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    assert [e["signature"] for e in fake_step.finalised[-1]["fault_entries"]] == ["in-b"]



def test_the_scored_evidence_keeps_step_level_faults_that_have_no_run(fake_step):                  # L-5 ruling
    faults.record(HarnessFault("infra-container", "in-a"), "dry9", "control", 2, 1, run="a")
    faults.record(HarnessFault("hand-edit", "scope"), "dry9", "control", 2, 0)             # no run: step-level
    fake_step.progress = [3]
    stepflow.run_step(fake_step.ctx, "go")
    assert [e["signature"] for e in fake_step.finalised[-1]["fault_entries"]] == ["scope"]


def test_run_a_records_whether_the_code_check_could_run(fake_step, monkeypatch):                # fix round 2
    _run_a(fake_step)
    real = stepflow.drive.run_attempt

    def with_check(c, attempt, message, resume=None, **kw):
        r = real(c, attempt, message, resume, **kw)
        r.outcome, r.code_check = "discovery-stop", {"status": "unavailable", "reasons": [{"turn": 0, "reason": "x"}]}
        return r
    monkeypatch.setattr(stepflow.drive, "run_attempt", with_check)
    stepflow.run_step(fake_step.ctx, "go", run="a")
    rec = json.loads((fake_step.ctx.out / "discovery.json").read_text())
    assert rec["code_check"]["status"] == "unavailable"
    assert faults.for_step("dry9", "control", 2) == []                   # never a harness fault


def test_run_a_records_the_code_check_when_it_ends_parked(fake_step, monkeypatch):               # fix round 3
    _run_a(fake_step)
    real = stepflow.drive.run_attempt

    def parked(c, attempt, message, resume=None, **kw):
        r = real(c, attempt, message, resume, **kw)
        r.outcome, r.park = "parked", PARK
        r.code_check = {"status": "unavailable", "reasons": [{"turn": 1, "reason": "x"}]}
        return r
    monkeypatch.setattr(stepflow.drive, "run_attempt", parked)
    stepflow.run_step(fake_step.ctx, "go", run="a")
    assert json.loads((fake_step.ctx.out / "parked.json").read_text())["code_check"]["status"] == "unavailable"


# ---- final fix batch A1: the tests phase (after the arm's attempt) is fault-handled too ------------------------------

def _fail_first(monkeypatch, target, name, exc, n=1):
    """`target.name` raises `exc` on its first `n` calls, then behaves as before."""
    real, calls = getattr(target, name), []

    def f(*a, **k):
        calls.append(1)
        if len(calls) <= n:
            raise exc
        return real(*a, **k)
    monkeypatch.setattr(target, name, f)
    return calls


@pytest.mark.parametrize("exc", [stepflow.docker.ContainerError("export failed in container (1): boom"),
                                 __import__("subprocess").TimeoutExpired(["docker", "run"], 600)])
def test_a_container_error_preparing_the_hidden_tests_is_infra_hidden_and_retests_the_same_commit(
        fake_step, monkeypatch, exc):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.hidden, "prepare", exc)
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-hidden" and e["run"] == "b" and e["attempt"] == 1
    assert fake_step.calls == 1 and fake_step.restored == []          # no new arm session, nothing restored
    assert out.status == "done" and out.attempts == 1


def test_a_hidden_collection_failure_is_infra_hidden_and_retests_the_same_commit(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.hidden, "run", stepflow.hidden.HiddenError("hidden collection failed: x"))
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert (e["kind"], e["signature"]) == ("infra-hidden", "hidden collection failed: x")
    assert fake_step.calls == 1 and fake_step.prepares == 2 and out.status == "done"


def test_a_container_error_in_quality_is_infra_quality_and_reruns_quality_only(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.quality, "run_all", stepflow.docker.ContainerError("mypy container died"))
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-quality" and fake_step.calls == 1 and fake_step.hidden_runs == 1
    assert fake_step.quality_runs == 1 and out.status == "done"


def test_a_git_error_writing_the_evidence_is_infra_evidence_and_rewrites_it(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.evidence, "finalise", stepflow.docker.ContainerError("git state failed"))
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-evidence" and fake_step.calls == 1 and len(fake_step.finalised) == 1
    assert out.status == "done"


def test_the_same_tests_phase_fault_twice_halts(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.hidden, "prepare", stepflow.docker.ContainerError("export failed"), n=2)
    with pytest.raises(stepflow.Halt):
        stepflow.run_step(fake_step.ctx, "go")
    assert [e["action"] for e in faults.entries("dry9")] == ["rerun", "halt"] and fake_step.calls == 1


def test_a_runner_bug_in_the_tests_phase_still_propagates(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.hidden, "run", KeyError("a runner bug"))
    with pytest.raises(KeyError):
        stepflow.run_step(fake_step.ctx, "go")
    assert faults.for_step("dry9", "control", 2) == []


def test_an_owner_park_at_the_idle_prompt_returns_a_parked_step(fake_step, monkeypatch):
    fake_step.progress = [3]

    def busy(ctx):
        stepflow._confirm_or_pause(ctx, "The machine is not idle. Run the hidden tests anyway?")
    monkeypatch.setattr(stepflow, "wait_idle", busy)
    fake_step.ctx.owner.confirm = lambda text: PARK
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "parked" and out.park == PARK and out.attempts == 1
    rec = json.loads((fake_step.ctx.out / "parked.json").read_text())
    assert rec["phase"] == "tests" and rec["attempt"] == 1


def test_an_owner_park_at_the_retest_prompt_returns_a_parked_step(fake_step):
    fake_step.progress = [3]
    fake_step.attribution_on = {1: ("harness-fault: pytest exit 137", [])}
    fake_step.ctx.owner.confirm = lambda text: PARK
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "parked" and out.park == PARK
    assert json.loads((fake_step.ctx.out / "parked.json").read_text())["phase"] == "tests"


def test_a_step_parked_in_its_tests_phase_resumes_at_the_tests_without_a_new_arm_session(fake_step):
    fake_step.progress = [3]
    fake_step.attribution_on = {1: ("harness-fault: pytest exit 137", [])}
    answers = [PARK, True]
    fake_step.ctx.owner.confirm = lambda text: answers.pop(0) if answers else True
    assert stepflow.run_step(fake_step.ctx, "go").status == "parked"
    assert (fake_step.ctx.out / stepflow.PENDING).is_file()
    fake_step.attribution_on = {}
    out = stepflow.run_step(fake_step.ctx, "go")                        # the caller runs the step again
    assert out.status == "done" and out.attempts == 1 and fake_step.calls == 1
    assert not (fake_step.ctx.out / stepflow.PENDING).exists()
    [k] = fake_step.finalised
    assert len(k["attempts"]) == 1 and k["attempts"][0].turns[0].stream_path is not None


def test_a_crash_in_the_tests_phase_resumes_at_the_tests(fake_step, monkeypatch):
    fake_step.progress = [0, 3]
    real = stepflow.hidden.run
    n = []

    def run(*a, **k):
        n.append(1)
        if len(n) == 2:
            raise KeyboardInterrupt("killed")
        return real(*a, **k)
    monkeypatch.setattr(stepflow.hidden, "run", run)
    with pytest.raises(KeyboardInterrupt):
        stepflow.run_step(fake_step.ctx, "go")                          # attempt 1 no progress, attempt 2 crashed
    assert json.loads((fake_step.ctx.out / stepflow.PENDING).read_text())["attempt"] == 2
    out = stepflow.run_step(fake_step.ctx, "go")
    assert fake_step.calls == 2 and out.status == "done" and out.attempts == 2
    assert len(fake_step.finalised[-1]["attempts"]) == 2


def test_an_arm_with_no_main_is_scored_all_failed_as_one_attempt(fake_step, monkeypatch):
    fake_step.progress = [0, 0, 0]
    monkeypatch.setattr(stepflow.gitops, "main_sha", lambda p: None)
    got = []

    def all_failed(p, step, out, why):
        got.append(why)
        return stepflow.hidden.summarise(step, {"m::t": "failed"}, ["m::t"], [], [], -1, attribution=why)
    monkeypatch.setattr(stepflow.hidden, "all_failed", all_failed, raising=False)
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and out.attempts == 3 and fake_step.prepares == 0
    assert got == [stepflow.hidden.NO_MAIN] * 3 and faults.for_step("dry9", "control", 2) == []
    assert fake_step.quality_runs == 0 and fake_step.finalised[-1]["quality"] == {"skipped": stepflow.hidden.NO_MAIN}


# ---- final fix batch A2: a network failure installing the arm's project is not the arm's ----------------------------

def test_an_infra_sync_fault_is_retested_on_the_same_commit_and_never_counts_as_an_arm_attempt(fake_step, monkeypatch):
    fake_step.progress = [3]
    _fail_first(monkeypatch, stepflow.hidden, "prepare",
                HarnessFault("infra-sync", "dns error: failed to lookup address", "hidden copy: dns error"))
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 2)
    assert e["kind"] == "infra-sync" and fake_step.calls == 1 and out.attempts == 1 and out.status == "done"
    got = json.loads((fake_step.ctx.out / "hidden" / "summary.json").read_text())
    assert [r["kind"] for r in got["harness_retests"]] == ["infra-sync"]


# ---- final fix batch A4: a substitute step-6 bug is scored by its acceptance test ------------------------------------

def _substitute(fs, monkeypatch, outcomes, baseline=None):
    """Step 6 with a substitute: `outcomes` are successive run_acceptance results ("passed"/"failed"/"error")."""
    fs.ctx.step = 6
    fs.ctx.acceptance = {"body": "def test_sub(): ...", "baseline": baseline or {"m::t": "passed"}}
    got = []

    def run_acceptance(p, copy, step, body):
        got.append(body)
        o = outcomes.pop(0)
        return {"outcome": o, "tests": {"tests.hidden.test_zz_substitute::test_sub": o}} if o != "error" else \
            {"outcome": "error", "detail": "container did not finish"}
    monkeypatch.setattr(stepflow.hidden, "run_acceptance", run_acceptance)
    return got


def test_a_substitute_step_is_not_done_until_its_acceptance_test_passes(fake_step, monkeypatch):
    fake_step.progress = [3, 3, 3]                   # the standard step-6 tests already pass (why it was substituted)
    got = _substitute(fake_step, monkeypatch, ["failed", "passed"])
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "done" and out.attempts == 2 and got == ["def test_sub(): ..."] * 2
    assert fake_step.messages == ["go", fake_step.no_progress]
    s = json.loads((fake_step.ctx.out / "hidden" / "summary.json").read_text())
    assert s["acceptance"]["outcome"] == "passed" and s["acceptance"]["progress"] is True


def test_a_substitute_arm_that_never_fixes_it_stops_after_three_attempts(fake_step, monkeypatch):
    fake_step.progress = [3, 3, 3]
    _substitute(fake_step, monkeypatch, ["failed"] * 3)
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and out.attempts == 3


def test_a_substitute_fix_that_breaks_a_passing_hidden_test_is_no_progress(fake_step, monkeypatch):
    fake_step.progress = [0, 3]                      # attempt 1: m::t now fails (a regression)
    _substitute(fake_step, monkeypatch, ["passed", "passed"])
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.attempts == 2
    [(k, label)] = fake_step.parked
    assert label == "no-progress"


def test_an_acceptance_run_that_did_not_complete_is_infra_hidden_retested(fake_step, monkeypatch):
    fake_step.progress = [3]
    _substitute(fake_step, monkeypatch, ["error", "passed"])
    out = stepflow.run_step(fake_step.ctx, "go")
    [e] = faults.for_step("dry9", "control", 6)
    assert e["kind"] == "infra-hidden" and out.status == "done" and fake_step.calls == 1


def test_an_install_failure_is_the_substitutes_failure_without_running_it(fake_step, monkeypatch):
    fake_step.progress = [3, 3, 3]
    got = _substitute(fake_step, monkeypatch, [])
    monkeypatch.setattr(stepflow.hidden, "prepare", lambda *a, **k: stepflow.hidden.Prepared(
        fake_step.ctx.out, None, {"hidden": {"ok": False}}))
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and got == []
    assert json.loads((fake_step.ctx.out / "hidden" / "summary.json").read_text())["acceptance"]["outcome"] == "failed"


def test_without_a_substitute_step6_progress_is_the_standard_rule(fake_step):
    fake_step.ctx.step = 6
    fake_step.progress = [3]
    assert stepflow.run_step(fake_step.ctx, "go").status == "done"


# ---- final fix batch A5: arm-caused events are arm violations and never halt ------------------------------------------

def _violations(fs):
    f = fs.ctx.out / "arm-violations.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


@pytest.mark.parametrize("check", ["common.git-identity", "common.origin", "common.no-foreign-plugins"])
def test_setup_drift_caused_by_the_arm_fails_the_attempt_and_is_repaired_by_restore(fake_step, check):
    fake_step.progress = [3, 3]
    fake_step.drift_on = {1: [check]}
    out = stepflow.run_step(fake_step.ctx, "go")
    [v] = _violations(fake_step)
    assert (v["kind"], v["check"], v["attempt"], v["run"]) == ("setup-drift", check, 1, "b")
    assert faults.for_step("dry9", "control", 2) == [] and not faults.halted("dry9")      # never the ledger
    assert fake_step.all_failed == ["arm-violation: setup-drift"] and fake_step.restored == [2]
    assert fake_step.messages == ["go", "go"] and fake_step.hidden_runs == 1          # a fresh session after the repair
    assert out.status == "done" and out.attempts == 2


def test_the_same_drift_twice_never_halts(fake_step):
    fake_step.progress = [0, 0, 0]
    fake_step.drift_on = {1: ["common.origin"], 2: ["common.origin"], 3: ["common.origin"]}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and out.attempts == 3 and len(_violations(fake_step)) == 3
    assert faults.entries("dry9") == []


def test_a_drift_on_the_last_attempt_is_still_repaired(fake_step):
    fake_step.progress = [0, 0, 0]
    fake_step.drift_on = {3: ["common.origin"]}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert out.status == "stopped" and fake_step.restored == [2]


def test_other_step_checks_are_not_arm_violations_here(fake_step):
    fake_step.progress = [3]
    fake_step.drift_on = {1: ["common.clean-green"]}
    out = stepflow.run_step(fake_step.ctx, "go")
    assert _violations(fake_step) == [] and out.status == "done"


def test_the_arm_printing_its_own_token_is_redacted_and_fails_the_attempt_without_halting(fake_step):
    fake_step.progress = [3, 3]
    fake_step.leak_on = {1}
    out = stepflow.run_step(fake_step.ctx, "go")
    [v] = _violations(fake_step)
    assert v["kind"] == "own-token-in-evidence" and v["files"] and faults.entries("dry9") == []
    assert fake_step.all_failed == ["arm-violation: own-token-in-evidence"]
    assert fake_step.messages == ["go", fake_step.no_progress] and fake_step.restored == []
    assert out.status == "done" and out.attempts == 2


def test_an_oom_killed_session_twice_is_arm_resource_all_failed_and_counted(fake_step):
    fake_step.progress = [3, 3]
    fake_step.oom_on = {1: 2}
    out = stepflow.run_step(fake_step.ctx, "go")
    [r] = faults.resource_records("dry9", 2)
    assert (r["exhausted"], r["attempt"]) == ("repeat", 1) and faults.entries("dry9") == []
    assert fake_step.all_failed == ["arm-resource: session"] and out.attempts == 2 and out.status == "done"


def test_an_oom_killed_session_that_recovered_is_recorded_once(fake_step):
    fake_step.progress = [3]
    fake_step.oom_on = {1: 1}
    stepflow.run_step(fake_step.ctx, "go")
    [r] = faults.resource_records("dry9", 2)
    assert r["exhausted"] == "once" and fake_step.all_failed == []


def test_run_a_records_arm_violations_and_resource_and_still_discovers(fake_step):
    _run_a(fake_step)
    fake_step.outcome_on = {1: "discovery-stop"}
    fake_step.drift_on = {1: ["common.origin"]}
    fake_step.leak_on = {1}
    out = stepflow.run_step(fake_step.ctx, "go", run="a")
    assert {v["kind"] for v in _violations(fake_step)} == {"setup-drift", "own-token-in-evidence"}
    assert out.status == "discovered" and faults.entries("dry9") == []


def test_an_acceptance_run_killed_for_resources_is_recorded_and_failed_not_a_fault(fake_step, monkeypatch):  # FU 4
    fake_step.progress = [3, 3]
    _substitute(fake_step, monkeypatch, ["passed"])
    real = stepflow.hidden.run_acceptance
    first = []

    def acc(p, copy, step, body):
        if not first:
            first.append(1)
            return {"outcome": "failed", "attribution": "arm-resource", "resource_evidence": [["oom-kill:1"]] * 2}
        return real(p, copy, step, body)
    monkeypatch.setattr(stepflow.hidden, "run_acceptance", acc)
    out = stepflow.run_step(fake_step.ctx, "go")
    assert faults.for_step("dry9", "control", 6) == [] and out.attempts == 2 and out.status == "done"
    [r] = faults.resource_records("dry9", 6)
    assert (r["exhausted"], r["attempt"]) == ("repeat", 1)
