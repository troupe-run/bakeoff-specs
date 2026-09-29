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


def test_run_a_stops_at_the_first_gate_or_code_and_restores_the_pre_step_snapshot(fake_step):
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
