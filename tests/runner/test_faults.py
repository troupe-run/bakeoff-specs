# Task 22: the harness-fault ledger and the halt rule (design §9).
import json
import pytest
from runner import cli, config, faults, paths
from runner.faults import HarnessFault


@pytest.fixture(autouse=True)
def ledger(tmp_state):
    return tmp_state


# ---- the plan's tests (brief Step 1) ----------------------------------------------------------------------------

def test_first_occurrence_reruns_second_identical_one_halts():
    f = HarnessFault("model-pin", "claude-haiku-4-5")
    assert faults.record(f, "pass1", "superpowers", 3, 1) == "rerun"
    assert faults.record(f, "pass1", "openspec", 1, 1) == "halt"        # same fault, any arm
    assert faults.halted("pass1") and faults.halted("pass2")          # real passes share one ledger


def test_dry_passes_have_their_own_ledger():
    f = HarnessFault("model-pin", "claude-haiku-4-5")
    faults.record(f, "dry3", "dryrun-pinfault", 1, 1); faults.record(f, "dry3", "dryrun-pinfault", 1, 2)
    assert faults.halted("dry3") and not faults.halted("pass1")


def test_different_signatures_do_not_add_up():
    assert faults.record(HarnessFault("infra-api", "overloaded"), "pass1", "bmad", 2, 1) == "rerun"
    assert faults.record(HarnessFault("infra-api", "rate limited"), "pass1", "bmad", 2, 1) == "rerun"


def test_owner_resolution_resets_the_count():
    f = HarnessFault("flaky-test", "tests.hidden.test_step2_sync::test_x")
    faults.record(f, "pass1", "a", 2, 1); faults.record(f, "pass1", "a", 2, 1)
    faults.resume("pass1", "fixed the readiness wait")
    assert not faults.halted("pass1") and faults.record(f, "pass1", "a", 2, 1) == "rerun"


def test_for_step_returns_only_that_steps_entries():
    faults.record(HarnessFault("x", "1"), "pass1", "a", 2, 1); faults.record(HarnessFault("x", "2"), "pass1", "a", 3, 1)
    assert [e["signature"] for e in faults.for_step("pass1", "a", 2)] == ["1"]


def test_declare_records_a_manual_fault_with_its_scope():
    faults.declare("pass1", "a", 4, "brief-typo", "retest")
    [e] = faults.for_step("pass1", "a", 4)
    assert e["kind"] == "manual" and e["signature"] == "brief-typo" and e["scope"] == "retest"


# ---- additions ------------------------------------------------------------------------------------------------

def test_ledger_paths_are_the_shared_files_for_real_passes_and_namespaced_otherwise():
    assert faults.ledger_paths("pass1") == (paths.FAULTS, paths.HALTED) == faults.ledger_paths("pass2")
    assert faults.ledger_paths("dry3") == (paths.RESULTS / "dry3" / "faults.jsonl", paths.RESULTS / "dry3" / "HALTED")


def test_the_halted_file_names_both_occurrences():
    f = HarnessFault("model-pin", "claude-haiku-4-5", "arm: assistant f:1")
    faults.record(f, "dry3", "a", 1, 1); faults.record(f, "dry3", "b", 2, 1)
    h = json.loads(faults.halted("dry3"))
    assert (h["first"]["arm"], h["second"]["arm"]) == ("a", "b") and h["second"]["action"] == "halt"


def test_a_ledger_entry_records_which_run_of_the_step_it_came_from():
    faults.record(HarnessFault("x", "1"), "dry3", "a", 2, 1, run="a")
    [e] = faults.for_step("dry3", "a", 2)
    assert e["run"] == "a"


def test_a_resolution_is_not_returned_as_a_step_entry():
    faults.record(HarnessFault("x", "1"), "dry3", "a", 2, 1)
    faults.resume("dry3", "fixed")
    assert [e["signature"] for e in faults.for_step("dry3", "a", 2)] == ["1"]


def test_declare_refuses_an_unknown_scope():
    with pytest.raises(ValueError):
        faults.declare("pass1", "a", 4, "x", "everything")


def test_a_declared_fault_counts_towards_the_halt_rule():
    faults.declare("dry3", "a", 4, "brief-typo", "rerun-step")
    assert faults.record(HarnessFault("manual", "brief-typo"), "dry3", "b", 4, 1) == "halt"


def test_resource_exhaustion_is_recorded_per_pass_step_and_arm_and_is_not_a_ledger_fault():
    faults.record_resource("dry3", "a", 3, 1, "repeat", [["oom-kill:1"], ["oom-kill:2"]])
    faults.record_resource("dry3", "b", 3, 2, "once", [["pids-max:4"], []])
    faults.record_resource("dry3", "a", 4, 1, "repeat", [["tmp-full"], ["tmp-full"]])
    assert [(r["arm"], r["exhausted"]) for r in faults.resource_records("dry3", 3)] == [("a", "repeat"), ("b", "once")]
    assert faults.for_step("dry3", "a", 3) == [] and not faults.halted("dry3")


def test_resource_records_of_dry_passes_never_mix_with_real_ones():
    faults.record_resource("dry3", "a", 3, 1, "repeat", [])
    assert faults.resource_records("pass1", 3) == []


def test_the_suite_resource_threshold_is_one_pinned_value_of_two():
    assert config.load_pins().limits.suite_resource_arms == 2


# ---- CLI ------------------------------------------------------------------------------------------------------

def test_cli_faults_list_prints_the_ledger_of_a_pass(capsys):
    faults.record(HarnessFault("model-pin", "m"), "dry3", "a", 1, 1)
    assert cli.main(["faults", "list", "--pass", "dry3"]) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line)["signature"] == "m"


def test_cli_faults_list_without_a_pass_prints_the_real_ledger(capsys):
    faults.record(HarnessFault("model-pin", "real"), "pass1", "a", 1, 1)
    faults.record(HarnessFault("model-pin", "dry"), "dry3", "a", 1, 1)
    cli.main(["faults", "list"])
    out = capsys.readouterr().out
    assert "real" in out and "dry" not in out


def test_cli_faults_declare_rerun_step_records_and_marks_progress(tmp_state):
    assert cli.main(["faults", "declare", "dry3", "control", "4", "allowlist-narrow", "--scope", "rerun-step"]) == 0
    [e] = faults.for_step("dry3", "control", 4)
    assert e["kind"] == "manual" and e["scope"] == "rerun-step"
    assert json.loads(paths.Paths("dry3", "control").progress.read_text())["rerun"] == 4


def test_cli_faults_declare_retest_leaves_progress_alone(tmp_state):
    cli.main(["faults", "declare", "dry3", "control", "4", "flaky", "--scope", "retest"])
    assert not paths.Paths("dry3", "control").progress.exists()


def test_cli_faults_declare_keeps_existing_progress_keys(tmp_state):
    p = paths.Paths("dry3", "control").progress
    p.parent.mkdir(parents=True); p.write_text(json.dumps({"next_step": 5}))
    cli.main(["faults", "declare", "dry3", "control", "4", "x", "--scope", "rerun-step"])
    assert json.loads(p.read_text()) == {"next_step": 5, "rerun": 4}


def test_cli_faults_resume_records_the_resolution_and_clears_halted():
    f = HarnessFault("model-pin", "m")
    faults.record(f, "dry3", "a", 1, 1); faults.record(f, "dry3", "a", 1, 2)
    assert cli.main(["faults", "resume", "dry3", "--note", "re-pinned the image"]) == 0
    assert not faults.halted("dry3")


def test_cli_faults_resume_needs_a_note():
    with pytest.raises(SystemExit):
        cli.main(["faults", "resume", "dry3"])


def test_every_other_command_refuses_while_halted(capsys):
    f = HarnessFault("model-pin", "m")
    faults.record(f, "pass1", "a", 1, 1); faults.record(f, "pass1", "a", 1, 2)
    assert cli.main(["github-plan", "pass1"]) == 1
    assert "HALTED" in capsys.readouterr().out
    assert cli.main(["faults", "list"]) == 0                       # `faults …` still runs
