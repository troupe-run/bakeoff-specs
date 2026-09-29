"""Task 23 support pieces: an owner-review halt in the ledger (suite-resource), the substitute bug's acceptance test in
the tester (proved to FAIL on the step-5 commit before delivery), setting an arm's leftovers aside so the step-2
teammate commits on a clean main, and the CLI commands."""
import json

import pytest

from runner import bundle_unpack, cli, faults, gitops, hidden, orchestrate, paths, stepflow
from runner.paths import Paths


# ---- faults.halt -------------------------------------------------------------------------------------------------

def test_an_owner_review_halt_blocks_everything_until_resolved(tmp_state):
    faults.halt("pass1", "suite-resource at step 3 (design §9)", {"kind": "suite-resource", "signature": "3"})
    assert "suite-resource" in faults.halted("pass1") and faults.halted("pass2")      # real passes share it
    assert cli.main(["status"]) == 1
    faults.resume("pass1", "memory limit raised")
    assert faults.halted("pass1") is None


# ---- the substitute bug's acceptance test --------------------------------------------------------------------------

def test_the_acceptance_test_travels_in_the_harness_bundle_never_a_mount():
    files = dict(bundle_unpack.parse(hidden.harness_bundle({hidden.SUBSTITUTE_TEST: b"def test_x(): pass\n"})))
    assert files[hidden.SUBSTITUTE_TEST] == b"def test_x(): pass\n" and "tests/hidden/conftest.py" in files


@pytest.mark.parametrize("bad", ["../x.py", "tests/hidden/../../x.py", "/etc/x.py", "tests/x.py"])
def test_an_extra_bundle_file_must_stay_inside_the_hidden_suite(bad):
    with pytest.raises(ValueError):
        hidden.harness_bundle({bad: b""})


def _junit(outcomes):
    cases = "".join(f'<testcase classname="tests.hidden.test_zz_substitute" name="{n}">'
                    + ("<failure message='x'/>" if o == "failed" else "") + "</testcase>" for n, o in outcomes.items())
    return f"<testsuites><testsuite>{cases}</testsuite></testsuites>".encode()


@pytest.mark.parametrize("outcomes,exit_,want", [({"test_a": "failed"}, b"1", "failed"),
                                                 ({"test_a": "passed"}, b"0", "passed"),
                                                 ({}, b"5", "error")])
def test_the_acceptance_verdict_is_read_from_the_junit(monkeypatch, outcomes, exit_, want):
    seen = {}

    def fake(p, copy, args, **k):
        seen.update(args=args, extra=k.get("extra"))
        return {"exit": exit_, "junit.xml": _junit(outcomes), "pytest.log": b""}, None
    monkeypatch.setattr(hidden, "_pytest", fake)
    r = hidden.run_acceptance(Paths("dry7", "dryrun"), paths.STATE / "copy", 6, "BODY")
    assert r["outcome"] == want
    assert seen["args"][:3] == [hidden.SUBSTITUTE_TEST, "--step", "6"] and seen["extra"] == {hidden.SUBSTITUTE_TEST: b"BODY"}


def test_a_run_that_could_not_complete_is_an_error_not_a_verdict(monkeypatch):
    monkeypatch.setattr(hidden, "_pytest", lambda *a, **k: (None, "container did not finish"))
    assert hidden.run_acceptance(Paths("dry7", "dryrun"), paths.STATE / "c", 6, "B")["outcome"] == "error"


# ---- set the arm's leftovers aside before the hand edit ------------------------------------------------------------

def test_leftovers_are_stashed_with_untracked_files_and_main_checked_out(monkeypatch):
    calls = []

    def git(p, *args, write=False, env=None, **k):
        calls.append((args, write, env))
        return type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})()
    monkeypatch.setattr(gitops, "git", git)
    monkeypatch.setattr(gitops, "state", lambda p: gitops.RepoState("feature", True, "h", "m", False))
    rec = gitops.set_aside_to_main(Paths("pass1", "control"), "leftovers at the end of step 1")
    (stash, w1, env1), (checkout, w2, _) = calls
    assert stash[:4] == ("stash", "push", "--include-untracked", "-m") and "leftovers" in stash[4]
    assert w1 and env1["GIT_COMMITTER_NAME"] == gitops.IDENTITY[0]
    assert checkout == ("checkout", "-q", "main") and w2
    assert rec == {"branch": "feature", "dirty": True, "stashed": True, "checked_out_main": True,
                   "aside_branch": None}


def test_a_clean_tree_on_main_is_left_alone(monkeypatch):
    monkeypatch.setattr(gitops, "git", lambda *a, **k: pytest.fail("no git write expected"))
    monkeypatch.setattr(gitops, "state", lambda p: gitops.RepoState("main", False, "h", "h", True))
    assert gitops.set_aside_to_main(Paths("pass1", "control"), "x") == {"branch": "main", "dirty": False,
                                                                       "stashed": False, "checked_out_main": False,
                                                                       "aside_branch": None}


# ---- the CLI --------------------------------------------------------------------------------------------------

def test_cli_order_records_and_prints_the_order(tmp_state, capsys):
    assert cli.main(["order", "pass1", "--seed", "3"]) == 0
    assert capsys.readouterr().out.split() == orchestrate.order("pass1", 3)


def test_cli_run_pass_prints_a_halt_and_exits_2(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_real_cred_owner", lambda: (None, None))

    def halt(pass_, cred, owner):
        raise stepflow.Halt('{"reason": "same harness fault twice"}')
    monkeypatch.setattr(orchestrate, "run_pass", halt)
    assert cli.main(["run-pass", "pass1"]) == 2
    assert "HALTED" in capsys.readouterr().out


def test_cli_run_arm_prints_a_refusal_and_exits_1(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (None, None))

    def no(*a, **k):
        raise orchestrate.NotReady("setup checklist is not green")
    monkeypatch.setattr(orchestrate, "run_arm", no)
    assert cli.main(["run-arm", "canary", "control"]) == 1
    assert "not green" in capsys.readouterr().out


def test_cli_run_arm_prints_the_result(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (None, None))
    monkeypatch.setattr(orchestrate, "run_arm", lambda *a, **k: {"completed": True})
    assert cli.main(["run-arm", "canary", "control"]) == 0
    assert json.loads(capsys.readouterr().out) == {"completed": True}


def test_cli_status_and_close_out(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(orchestrate, "status", lambda: "pass1 control 1:a=discovered")
    assert cli.main(["status"]) == 0 and "1:a=discovered" in capsys.readouterr().out
    monkeypatch.setattr(cli, "_real_owner", lambda: None)
    monkeypatch.setattr(orchestrate, "close_out", lambda pass_, owner: paths.RESULTS / "x.md")
    assert cli.main(["close-out", "pass1"]) == 0


def test_cli_images_build_only_builds_the_named_images(tmp_state, monkeypatch, capsys):
    from runner import images
    got = []
    monkeypatch.setattr(images, "build_only", lambda names: got.append(names) or {"arms": {}, "images": {}})
    assert cli.main(["images", "build", "--only", "tester_ref", "openspec"]) == 0
    assert got == [["tester_ref", "openspec"]]


def test_cli_setup_again_goes_through_orchestration(tmp_state, monkeypatch, capsys):
    from runner import checklist
    got = []
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (None, None))
    monkeypatch.setattr(orchestrate, "setup", lambda pass_, arm, cred, owner, again=False:
                        got.append((pass_, arm, again)) or checklist.SetupResult([], {}, True, 0.0))
    assert cli.main(["setup", "pass1", "control", "--again"]) == 0
    assert got == [("pass1", "control", True)]
