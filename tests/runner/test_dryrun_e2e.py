"""Task 24: the whole runner end to end — `runner dry-run --report` once per module, then its evidence checked.

The fake claude in `bakeoff-arm-dryrun:1` plays the arm (with the reference implementation), the PO and the teammate;
the credential is the dummy and the owner is scripted: no model is called and GitHub is never touched. Everything
else is real: containers, egress stages, containerised git, snapshots, the turn loop, escalation and brief growth (on
a copy of the brief), owner gates, the hand edit, the dry tracker, hidden tests in the tester, quality tools,
evidence, model-pin checks, fault classification, the stop rules and the secret scan.

Each pass is the owner's step-major structure (2026-09-29, Task 23 rulings): for every step, N.a (discovery: stops
at the first approval request or code edit, unscored, reset), the consistency check, then N.b (scored). Run with
`--run-docker`, under the docker lock; it takes a while."""
import json, subprocess

import pytest

from runner import handoff, secrets
from runner.paths import RESULTS, REPO_ROOT, STATE

pytestmark = pytest.mark.docker
EXPECTED = {1: 101, 2: 109, 3: 121, 4: 135, 5: 146, 6: 151, 7: 161}


@pytest.fixture(scope="module", autouse=True)
def dry_runs():
    r = subprocess.run(["uv", "run", "python", "-m", "runner", "dry-run", "--report"], cwd=REPO_ROOT, timeout=14400,
                       capture_output=True, text=True)
    (RESULTS / "dryrun-cli.log").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    return r


def J(*p): return json.loads(RESULTS.joinpath(*p).read_text())
def lines(*p): return [json.loads(l) for l in RESULTS.joinpath(*p).read_text().splitlines() if l.strip()]


def test_the_report_says_pass(dry_runs):
    assert dry_runs.returncode == 0, dry_runs.stdout[-3000:] + dry_runs.stderr[-3000:]
    assert (RESULTS / "dryrun-validation.md").read_text().rstrip().endswith("**Result: PASS**")


# ---- dry1: the happy path ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("step", range(1, 8))
def test_dry1_hidden_results_match_the_validated_reference_counts(step):
    s = J("dry1", "dryrun", f"{step:02d}", "hidden", "summary.json")
    assert (s["total"], s["passed"], s["failed"], s["flaky"], s["flaky_arm"]) == (EXPECTED[step], EXPECTED[step], 0, 0, 0)


@pytest.mark.parametrize("step", range(1, 8))
def test_dry1_every_step_has_the_design_7_evidence_and_a_pin_report_without_violations(step):   # renamed (Q-11)
    d = RESULTS / "dry1" / "dryrun" / f"{step:02d}"
    for rel in ["run.json", "cost.json", "questions.jsonl", "git.json", "summary.md", "quality/summary.json", "handoff.md",
                "a/discovery.json", "a/questions.jsonl", "a/model-pin.json", "a/handoff.md"]:
        assert (d / rel).exists(), rel
    for pin in (J("dry1", "dryrun", f"{step:02d}", "model-pin.json"), J("dry1", "dryrun", f"{step:02d}", "a", "model-pin.json")):
        assert pin["ok"] and pin["assistant_messages"] > 0 and not pin["violations"]
    assert J("dry1", "dryrun", f"{step:02d}", "git.json")["sha_after"]           # refs/heads/main recorded (F-1)


def test_dry1_each_step_ran_discovery_then_the_consistency_check_then_the_scored_run():   # Task 23 rulings
    ended = [(e["step"], e["run"]) for e in lines("dry1", "run-log.jsonl") if e["event"] == "run-ended"]
    assert ended == [(n, r) for n in range(1, 8) for r in ("a", "b")]
    for n in range(1, 8):
        a = J("dry1", "dryrun", f"{n:02d}", "a", "discovery.json")
        # N.a stops at the first code edit (step 1: the arm asks, then writes code) or the first approval request
        assert a["outcome"] == "discovery-stop" and a["discovery"]["why"] == ("code" if n == 1 else "approval"), n
        # the reset: N.b starts from the same pre-step commit N.a did
        assert a["sha_before"] == J("dry1", "dryrun", f"{n:02d}", "git.json")["sha_before"], n
        assert J("dry1", "consistency", f"step-{n:02d}.json")["status"] in ("confirmed", "nothing-new"), n
    c1 = J("dry1", "consistency", "step-01.json")
    assert c1["status"] == "confirmed" and "floats exactly as written" in json.dumps(c1["rounds"][0]["groups"])
    log = [e["event"] for e in lines("dry1", "run-log.jsonl")]
    first_b = next(i for i, e in enumerate(lines("dry1", "run-log.jsonl")) if e["event"] == "run-ended" and e["run"] == "b")
    assert "consistency-confirmed" in log[:first_b]                      # the owner confirmed before 1.b


def test_dry1_escalation_in_1a_reached_the_owner_grew_the_copy_and_1b_got_the_same_answer_from_the_po():
    qa = lines("dry1", "dryrun", "01", "a", "questions.jsonl")
    assert any(e["escalated"] and "owner" in e["answered_by"] for e in qa)
    qb = [e for e in lines("dry1", "dryrun", "01", "questions.jsonl") if e["kind"] == "question"]
    assert qb and all(e["answered_by"] == "po" and not e["escalated"] for e in qb)
    assert qb[0]["reply"] == "Print floats exactly as written in the file."
    assert "print floats exactly as written" in (STATE / "dry1" / "po-brief.md").read_text().lower()
    assert subprocess.run(["git", "diff", "--quiet", "scenario/po-brief.md"], cwd=REPO_ROOT).returncode == 0


def test_dry1_approvals_went_through_the_owner_gate():
    gates = lines("dry1", "dryrun", "02", "owner-gates.jsonl")
    assert gates and gates[0]["owner_action"] == "accept" and gates[0]["final_reply"] == "Approved: consistent with the contract."


def test_dry1_hand_edit_was_verified_and_detection_facts_recorded():
    assert all(J("dry1", "dryrun", "02", "hand-edit", "probe.json").values())
    assert J("dry1", "dryrun", "02", "hand-edit", "detection.json")["feature_kept"] is True
    assert J("dry1", "dryrun", "02", "hand-edit", "edit.json")["files"] == ["src/troupe_ref/cli.py"]
    assert "session_mentions" in J("dry1", "dryrun", "02", "hand-edit", "detection-a.json")      # 2.a, recorded


def test_dry1_step3_followed_the_methods_next_command_and_ran_must_run():
    q = lines("dry1", "dryrun", "03", "questions.jsonl")
    assert [e["reply"] for e in q if e["kind"] in ("next_command", "step_done") and e["reply"]] == ["/dry-next", "/dry-close"]


def test_dry1_step5_was_two_requests():                                          # OD6 B
    kinds = [e["kind"] for e in lines("dry1", "dryrun", "05", "questions.jsonl")]
    assert "preempted" in kinds and "A second change request" in (RESULTS / "dry1/dryrun/05/handoff.md").read_text()


def test_dry1_step6_bug_went_to_the_tracker():
    assert J("dry1", "dryrun", "06", "tracker.json")["issues"][0]["ref"] == "dry#1"
    assert J("dry1", "dryrun", "06", "precheck", "precheck.json")["planted_already_passes"] is False


def test_dry1_mutation_score_was_measured_on_copy_b():                           # m-10: asserts copy B
    prep = J("dry1", "dryrun", "07", "hidden", "prep-07-a1.json")
    # copy B is the only copy with mutmut installed (review C-1): its own sync record, ok, installs it; copy A's not
    assert prep["quality"]["ok"] is True and "mutmut-requirements.txt" in prep["quality"]["command"]
    assert "mutmut" not in prep["hidden"]["command"]
    # and the mutation run used that copy's venv mutmut (absent from copy A, so it cannot have run there)
    assert "$ .venv/bin/mutmut run" in (RESULTS / "dry1/dryrun/07/quality/mutmut.log").read_text()
    assert J("dry1", "dryrun", "07", "quality", "summary.json")["mutation"]["total"] > 0


def test_no_credential_in_any_evidence_state_or_container_spec():               # strengthened (review Q-11)
    for root in [RESULTS / f"dry{i}" for i in range(1, 5)] + [STATE / f"dry{i}" for i in range(1, 5)]:
        assert secrets.scan_tree(root, ["dry-run-dummy-token"]) == [], root      # .gz files are decompressed
    rep = json.loads((RESULTS / "dryrun-specs.json").read_text())
    assert rep["specs"] > 100 and rep["specs_containing_token"] == 0              # every RunSpec the dry run built
    assert subprocess.run(["docker", "ps", "-aq", "--filter", "label=bakeoff.run"], capture_output=True,
                          text=True).stdout.strip() == ""


# ---- dry2: the arm stop rule ----------------------------------------------------------------------------------

def test_dry2_arm_stops_at_step2_after_three_no_progress_attempts():
    assert J("dry2", "dryrun-broken", "arm-result.json")["stopped_at"] == 2
    parked = sorted(p.name for p in (RESULTS / "dry2/dryrun-broken/02/attempts").iterdir())
    assert parked == ["1-no-progress", "2-no-progress"]
    assert not (RESULTS / "dry2/dryrun-broken/03").exists()
    prompts = [p.read_text() for p in sorted((RESULTS / "dry2/dryrun-broken/02/turns").glob("arm-a*-*.prompt.md"))]
    assert prompts.count(handoff.MESSAGES["no_progress"]) == 2                     # sent twice, in the same session
    assert J("dry2", "dryrun-broken", "02", "run.json")["outcome"] == "stopped"


# ---- dry3: the model pin and the halt rule ---------------------------------------------------------------------

def test_dry3_same_pin_fault_twice_halts():
    assert (RESULTS / "dry3" / "HALTED").exists()
    assert [e["signature"] for e in lines("dry3", "faults.jsonl")] == ["claude-haiku-4-5", "claude-haiku-4-5"]
    assert [e["action"] for e in lines("dry3", "faults.jsonl")] == ["rerun", "halt"]
    assert not (RESULTS / "HALTED").exists()                                     # the real ledger is untouched


# ---- dry4: transient error, turn timeout, pause and resume ------------------------------------------------------

def test_dry4_transient_error_was_retried_in_place_without_a_harness_fault():   # review C-4
    run = J("dry4", "dryrun-edge", "01", "run.json")
    assert any(i.startswith("transient-retry:") for i in run["interventions"])
    ledger = RESULTS / "dry4" / "faults.jsonl"
    assert not ledger.exists() or not any(e.get("kind", "").startswith("infra-") for e in lines("dry4", "faults.jsonl"))


def test_dry4_timeout_ended_an_attempt_as_an_arm_outcome_and_the_step_still_completed():
    run = J("dry4", "dryrun-edge", "02", "run.json")
    assert "turn_seconds" in run["breaches"] and run["attempts"] == 1 and run["outcome"] == "done"
    assert J("dry4", "dryrun-edge", "breaches.json")[0]["owner"] == "arm"


def test_dry4_paused_at_step1s_review_and_resumed_without_rerunning_step1_to_the_end():
    prog = json.loads((STATE / "dry4" / "dryrun-edge" / "progress.json").read_text())
    assert prog["steps"]["1"]["review"] == "pause"                       # the runner's own record of the pause
    ended = [(e["step"], e["run"]) for e in lines("dry4", "run-log.jsonl") if e["event"] == "run-ended"]
    assert ended.count((1, "b")) == 1                                    # the resume adopted 1.b, never re-ran it
    assert ended[-1] == (7, "b")
    assert J("dry4", "dryrun-edge", "resume.json")["paused_after"] == 1
    assert J("dry4", "dryrun-edge", "arm-result.json")["completed"] is True
