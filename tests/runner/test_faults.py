# Task 22: the harness-fault ledger and the halt rule (design §9).
import json
import pytest
from runner import cli, config, faults, paths
from runner.faults import HarnessFault


@pytest.fixture(autouse=True)
def ledger(tmp_state):
    (paths.RESULTS / "dry3").mkdir(parents=True)          # a dry pass that exists (declare/resume validate it)
    return tmp_state


# ---- the plan's tests (brief Step 1) ----------------------------------------------------------------------------

def test_first_occurrence_reruns_second_identical_one_halts():
    f = HarnessFault("model-pin", "claude-haiku-4-5")
    assert faults.record(f, "pass1", "superpowers", 3, 1) == "rerun"
    assert faults.record(f, "pass1", "openspec", 1, 1) == "halt"        # same fault, any arm
    assert faults.halted("pass1") and faults.ledger_paths("pass1")[0] == paths.FAULTS   # the real run's ledger


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
    faults.declare("pass1", "control", 4, "brief-typo", "retest")
    [e] = faults.for_step("pass1", "control", 4)
    assert e["kind"] == "manual" and e["signature"] == "brief-typo" and e["scope"] == "retest"


# ---- additions ------------------------------------------------------------------------------------------------

def test_ledger_paths_are_the_shared_files_for_real_passes_and_namespaced_otherwise():
    assert faults.ledger_paths("pass1") == (paths.FAULTS, paths.HALTED)
    assert faults.ledger_paths("pass2") == (paths.RESULTS / "pass2" / "faults.jsonl", paths.RESULTS / "pass2" / "HALTED")
    assert paths.REAL_PASSES == ("pass1",)                                # follow-up 10: pass 2 is retired
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
    faults.record(HarnessFault("x", "1"), "dry3", "a", 2, 1); faults.record(HarnessFault("x", "1"), "dry3", "a", 2, 2)
    faults.resume("dry3", "fixed")
    assert [e["signature"] for e in faults.for_step("dry3", "a", 2)] == ["1", "1"]


def test_declare_refuses_an_unknown_scope():
    with pytest.raises(ValueError):
        faults.declare("pass1", "control", 4, "x", "everything")


def test_a_declared_fault_counts_towards_the_halt_rule():                          # fix round 1 M-1
    assert faults.declare("dry3", "control", 4, "brief-typo", "rerun-step") == "rerun"
    assert faults.declare("dry3", "openspec", 5, "brief-typo", "retest") == "halt"
    h = json.loads(faults.halted("dry3"))
    assert (h["first"]["arm"], h["second"]["arm"]) == ("control", "openspec")


@pytest.mark.parametrize("pass_, arm, step, slug", [
    ("nosuchpass", "control", 4, "x"),          # not a known pass and nothing on disk
    ("../evil", "control", 4, "x"),             # would leave the results tree
    ("Pass1", "control", 4, "x"),
    ("dry3", "nosucharm", 4, "x"),
    ("dry3", "../control", 4, "x"),
    ("dry3", "control", 0, "x"), ("dry3", "control", 8, "x"),
    ("dry3", "control", 4, ""), ("dry3", "control", 4, "a b/c"),
])
def test_declare_refuses_bad_input_and_writes_nothing(pass_, arm, step, slug):                  # fix round 1 M-2
    with pytest.raises(ValueError):
        faults.declare(pass_, arm, step, slug, "retest")
    assert not paths.FAULTS.exists() and not (paths.RESULTS / "dry3" / "faults.jsonl").exists()
    assert sorted(x.name for x in paths.RESULTS.iterdir()) == ["dry3"]


def test_resume_needs_a_note():
    f = HarnessFault("m", "x"); faults.record(f, "dry3", "a", 1, 1); faults.record(f, "dry3", "a", 1, 2)
    with pytest.raises(ValueError):
        faults.resume("dry3", "   ")
    assert faults.halted("dry3")


def test_resume_refuses_a_pass_that_is_not_halted_and_appends_nothing():
    faults.record(HarnessFault("m", "x"), "dry3", "a", 1, 1)
    with pytest.raises(ValueError, match="not halted"):
        faults.resume("dry3", "nothing to resolve")
    assert [e.get("resolution") for e in faults.entries("dry3")] == [None]


def test_resume_refuses_an_unknown_pass():
    with pytest.raises(ValueError):
        faults.resume("../../etc", "x")


def test_resource_exhaustion_is_recorded_per_pass_step_and_arm_and_is_not_a_ledger_fault():
    faults.record_resource("dry3", "a", 3, 1, "repeat", [["oom-kill:1"], ["oom-kill:2"]], run="b")
    faults.record_resource("dry3", "b", 3, 2, "once", [["pids-max:4"], []], run="b")
    faults.record_resource("dry3", "a", 4, 1, "repeat", [["tmp-full"], ["tmp-full"]], run="b")
    assert [(r["arm"], r["exhausted"]) for r in faults.resource_records("dry3", 3)] == [("a", "repeat"), ("b", "once")]
    assert faults.for_step("dry3", "a", 3) == [] and not faults.halted("dry3")


def test_resource_records_of_dry_passes_never_mix_with_real_ones():
    faults.record_resource("dry3", "a", 3, 1, "repeat", [], run="b")
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


def test_cli_faults_resume_with_an_empty_note_is_a_clean_error(capsys):
    f = HarnessFault("m", "x"); faults.record(f, "dry3", "a", 1, 1); faults.record(f, "dry3", "a", 1, 2)
    assert cli.main(["faults", "resume", "dry3", "--note", ""]) == 2
    assert "note" in capsys.readouterr().err and faults.halted("dry3")


def test_cli_faults_resume_on_a_pass_that_is_not_halted_is_refused(capsys):
    assert cli.main(["faults", "resume", "dry3", "--note", "x"]) == 2
    assert "not halted" in capsys.readouterr().err and faults.entries("dry3") == []


def test_cli_faults_declare_with_a_bad_arm_is_a_clean_error_and_marks_no_progress(capsys):
    assert cli.main(["faults", "declare", "dry3", "nosucharm", "4", "x", "--scope", "rerun-step"]) == 2
    assert "arm" in capsys.readouterr().err
    assert not paths.Paths("dry3", "nosucharm").progress.exists()


def test_cli_faults_declare_the_same_slug_twice_halts(capsys):
    cli.main(["faults", "declare", "dry3", "control", "4", "x", "--scope", "retest"])
    assert cli.main(["faults", "declare", "dry3", "control", "4", "x", "--scope", "retest"]) == 1
    assert "HALTED" in capsys.readouterr().out and faults.halted("dry3")


def test_cli_faults_list_refuses_a_pass_outside_the_results_tree(capsys):
    assert cli.main(["faults", "list", "--pass", "../x"]) == 2


def test_every_other_command_refuses_while_halted(capsys):
    f = HarnessFault("model-pin", "m")
    faults.record(f, "pass1", "a", 1, 1); faults.record(f, "pass1", "a", 1, 2)
    assert cli.main(["github-plan", "pass1"]) == 1
    assert "HALTED" in capsys.readouterr().out
    assert cli.main(["faults", "list"]) == 0                       # `faults …` still runs


# ---- fix round 2 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("pass_, arm, slug", [("dry3\n", "control", "x"), ("dry3", "control\n", "x"),
                                              ("dry3", "control", "x\n")])
def test_a_trailing_newline_is_not_a_valid_name(pass_, arm, slug):
    with pytest.raises(ValueError):
        faults.declare(pass_, arm, 4, slug, "retest")
    assert not (paths.RESULTS / "dry3" / "faults.jsonl").exists()


def test_a_resource_record_must_say_which_run_it_came_from():                  # follow-up round 2, item 7
    with pytest.raises(TypeError):
        faults.record_resource("dry3", "a", 3, 1, "repeat", [])
    with pytest.raises(ValueError):
        faults.record_resource("dry3", "a", 3, 1, "repeat", [], run="c")


# ---- --scope record (owner, 2026-10-01): an owner stop, recorded as a harness fault, superseding nothing -----------

def test_declare_record_adds_the_ledger_entry_and_changes_no_step_state(tmp_state):
    prog = paths.Paths("dry3", "control").progress
    prog.parent.mkdir(parents=True)
    prog.write_text(json.dumps({"steps": {"4": {"b": {"status": "interrupted"}}}}))
    before = prog.read_text()
    assert cli.main(["faults", "declare", "dry3", "control", "4", "owner-stop-1", "--scope", "record"]) == 0
    [e] = faults.for_step("dry3", "control", 4)
    assert (e["kind"], e["signature"], e["scope"], e["action"]) == ("manual", "owner-stop-1", "record", "record")
    assert prog.read_text() == before                              # no `rerun` mark, nothing superseded
    assert not faults.halted("dry3")


def test_declare_record_with_the_same_slug_twice_halts(capsys):
    assert cli.main(["faults", "declare", "dry3", "control", "4", "owner-stop", "--scope", "record"]) == 0
    assert cli.main(["faults", "declare", "dry3", "control", "5", "owner-stop", "--scope", "record"]) == 1
    assert "HALTED" in capsys.readouterr().out and faults.halted("dry3")
