"""Task 24: the fake claude's scripted roles (arm, PO, teammate), run on the host as a plain script — no Docker, no
model. `FAKE_REFERENCE_DIR` and `FAKE_PO_DIR` stand in for the image's `/opt/reference` and the PO's `/po` mounts
(test-only overrides; the image never sets them)."""
import importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

import pytest

from runner import handedit, handoff, po
from runner.paths import REPO_ROOT

FAKE = REPO_ROOT / "runner" / "images" / "dryrun" / "fake_claude.py"
BRIEF = (REPO_ROOT / "scenario" / "po-brief.md").read_text()
CONTRACT = (REPO_ROOT / "scenario" / "contract.md").read_text()
STEPS = sorted((REPO_ROOT / "scenario" / "steps").glob("0*.md"))


def load_fake():
    spec = importlib.util.spec_from_file_location("fake_claude", FAKE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


F = load_fake()


# ---- the PO ------------------------------------------------------------------------------------------------------

def decide(message: str, brief: str = BRIEF) -> po.Decision:
    return po.parse(json.dumps(F.po_decision(message, brief)))


def test_po_escalates_the_float_question_while_the_brief_does_not_answer_it():
    d = decide("Before I start: should `config show` print floats exactly as written in the file?")
    assert d.kind == "question" and d.answers[0].escalate and d.answers[0].reply is None and d.significant


def test_po_answers_the_float_question_from_the_grown_brief_without_escalating():
    grown = BRIEF.rstrip() + ("\n- **Q:** Should `config show` print floats exactly as written in the file? **A:** "
                              "Print floats exactly as written in the file. _(2026-09-30; dry1; first raised by dryrun "
                              "at step 1; answered by the scripted owner)_\n")
    d = decide("Before I start: should `config show` print floats exactly as written in the file?", grown)
    assert d.kind == "question" and not d.answers[0].escalate
    assert d.answers[0].reply == "Print floats exactly as written in the file." and d.answers[0].cited


def test_po_approves_a_plan_names_the_next_command_and_sees_a_step_done():
    a = decide("Plan: implement step 2 as briefed. Do you approve?")
    assert (a.kind, a.approved, a.reply) == ("approval", True, "Approved: consistent with the contract.")
    n = decide("Done with the core; next, run /dry-next")
    assert (n.kind, n.command) == ("next_command", "/dry-next")
    assert decide("Step 4 is complete.").kind == "step_done"
    assert decide("Closed. Step 4 is complete.").kind == "step_done"
    c = decide("Working on it")
    assert (c.kind, c.reply) == ("continue", "Please continue.")


# ---- the arm: which step a message is ------------------------------------------------------------------------------

def test_the_step_comes_from_the_real_handoffs():
    for n, f in enumerate(STEPS, 1):
        if n == 5:
            first, second = handoff.step5(f.read_text(), CONTRACT)
            assert F.step_of(first) == 5 and F.step_of(second) == 5
        elif n == 6:
            assert F.step_of(handoff.bug_message("dry#1", CONTRACT)) == 6
        else:
            assert F.step_of(handoff.compose(n, f.read_text(), CONTRACT)) == n
    assert F.step_of("Please continue.") is None and F.step_of("/dry-close") is None


def test_the_teammate_is_recognised_by_its_fixed_prompt():
    assert F.role_of(handedit.PROMPT) == "teammate"
    assert F.role_of(po.MESSAGE) == "po"
    assert F.role_of("# Step 1 — troupe configuration") == "arm"


# ---- the arm and the teammate, as processes ---------------------------------------------------------------------

@pytest.fixture
def world(tmp_path):
    ref = tmp_path / "reference"
    shutil.copytree(REPO_ROOT / "reference", ref, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
    repo = tmp_path / "repo"; repo.mkdir()
    home = tmp_path / "home"; (home / ".claude").mkdir(parents=True)
    (home / ".gitconfig").write_text("[user]\n\tname = Developer\n\temail = developer@troupe.run\n"
                                     "[init]\n\tdefaultBranch = main\n")
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"),
           "FAKE_REFERENCE_DIR": str(ref), "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, env=env, check=True)
    return repo, env


def turn(world, message, resume=None, **extra_env):
    repo, env = world
    argv = [sys.executable, str(FAKE), "-p", message, "--model", "claude-opus-5-5", "--output-format", "stream-json"]
    if resume:
        argv += ["--resume", resume]
    r = subprocess.run(argv, cwd=repo, env={**env, **extra_env}, capture_output=True, text=True, timeout=60)
    events = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    init = next(e for e in events if e.get("type") == "system")
    res = next((e for e in events if e.get("type") == "result"), None)
    return init["session_id"], res, r


def git(world, *a):
    return subprocess.run(["git", *a], cwd=world[0], env=world[1], capture_output=True, text=True).stdout.strip()


def step_py(world):
    return (world[0] / "src" / "troupe_ref" / "step.py").read_text()


def test_step1_asks_then_copies_the_reference_as_step_1_and_commits(world):
    msg = handoff.compose(1, STEPS[0].read_text(), CONTRACT)
    sid, r, _ = turn(world, msg)
    assert "print floats exactly as written" in r["result"] and not r["is_error"]
    assert git(world, "rev-list", "--count", "HEAD") == "1"
    sid2, r, _ = turn(world, "Print floats exactly as written in the file.", sid)
    assert sid2 == sid and r["result"] == "Step 1 is complete."
    assert git(world, "log", "-1", "--format=%s") == "Step 1"
    assert {"pyproject.toml", "uv.lock", "src/troupe_ref/cli.py", "tests/test_aliases.py"} <= \
        set(git(world, "ls-files").splitlines())
    assert 'os.environ.get("TROUPE_REF_STEP", "1")' in step_py(world)       # behaves as step 1 unless told otherwise
    _, r, _ = turn(world, "Please continue.", sid)
    assert r["result"] == "Step 1 is complete." and git(world, "rev-list", "--count", "HEAD") == "2"


def _through_step1(world):
    sid, _, _ = turn(world, handoff.compose(1, STEPS[0].read_text(), CONTRACT))
    turn(world, "ok", sid)


def test_a_later_step_plans_then_commits_that_step_and_step3_offers_its_next_command(world):
    _through_step1(world)
    sid, r, _ = turn(world, handoff.compose(3, STEPS[2].read_text(), CONTRACT))
    assert r["result"] == "Plan: implement step 3 as briefed. Do you approve?"
    _, r, _ = turn(world, "Approved: consistent with the contract.", sid)
    assert r["result"] == "Done with the core; next, run /dry-next"
    assert git(world, "log", "-1", "--format=%s") == "Step 3" and '"TROUPE_REF_STEP", "3"' in step_py(world)
    assert turn(world, "/dry-next", sid)[1]["result"] == "Step 3 is complete."
    assert turn(world, "/dry-close", sid)[1]["result"] == "Closed. Step 3 is complete."


def test_step5_and_step6_messages_and_a_second_change_request(world):
    _through_step1(world)
    first, second = handoff.step5(STEPS[4].read_text(), CONTRACT)
    sid, r, _ = turn(world, first)
    assert r["result"] == "Plan: implement step 5 as briefed. Do you approve?"
    turn(world, "Approved.", sid)
    assert turn(world, second, sid)[1]["result"] == "Step 5 is complete."
    sid6, r, _ = turn(world, handoff.bug_message("dry#1", CONTRACT))
    assert r["result"] == "Plan: implement step 6 as briefed. Do you approve?"
    turn(world, "Approved.", sid6)
    assert '"TROUPE_REF_STEP", "6"' in step_py(world)


def test_broken_variant_pins_the_reference_to_step_1_at_step_2(world):
    _through_step1(world)
    sid, _, _ = turn(world, handoff.compose(2, STEPS[1].read_text(), CONTRACT), FAKE_VARIANT="broken")
    _, r, _ = turn(world, "Approved.", sid, FAKE_VARIANT="broken")
    assert r["result"] == "Step 2 is complete."
    assert 'STEP = min(int(os.environ.get("TROUPE_REF_STEP", "7")), 1)' in step_py(world)


def test_edge_variant_step1_first_turn_is_a_529_that_does_not_count(world):
    msg = handoff.compose(1, STEPS[0].read_text(), CONTRACT)
    sid, r, _ = turn(world, msg, FAKE_VARIANT="edge")
    assert r["is_error"] and r["result"].startswith("API Error: 529")
    _, r, _ = turn(world, "Please continue.", sid, FAKE_VARIANT="edge")          # the in-place retry
    assert not r["is_error"] and "print floats exactly as written" in r["result"]


def test_edge_variant_step2_first_turn_commits_then_hangs_after_its_evidence(world):
    _through_step1(world)
    repo, env = world
    argv = [sys.executable, str(FAKE), "-p", handoff.compose(2, STEPS[1].read_text(), CONTRACT),
            "--model", "claude-opus-5-5"]
    with pytest.raises(subprocess.TimeoutExpired) as e:
        subprocess.run(argv, cwd=repo, env={**env, "FAKE_VARIANT": "edge", "FAKE_EDGE_SLEEP": "30"},
                       capture_output=True, text=True, timeout=5)
    out = (e.value.stdout or b"").decode() if isinstance(e.value.stdout, bytes) else (e.value.stdout or "")
    assert '"type": "assistant"' in out and '"type": "result"' not in out     # evidence first, then the hang
    assert git(world, "log", "-1", "--format=%s") == "Step 2" and '"TROUPE_REF_STEP", "2"' in step_py(world)
    assert list((Path(env["CLAUDE_CONFIG_DIR"]) / "projects").rglob("*.jsonl"))


def test_the_teammate_makes_the_theatre_default_come_from_the_environment(world):
    _through_step1(world)
    _, r, _ = turn(world, handedit.PROMPT)
    assert r["result"] == "src/troupe_ref/cli.py"
    cli = (world[0] / "src" / "troupe_ref" / "cli.py").read_text()
    assert 'default=__import__("os").environ.get("TROUPE_THEATRE") or "."' in cli
    assert 'sp.add_argument("--theatre", default=".")' not in cli


def test_a_fake_directive_still_wins_for_every_role(world):
    _, r, _ = turn(world, "# Step 1 — x\nFAKE:reply=directive")
    assert r["result"] == "directive"
    _, r, _ = turn(world, handedit.PROMPT + "FAKE:reply=also")
    assert r["result"] == "also"


def test_the_po_reads_the_message_and_brief_from_its_mounts(world, tmp_path):
    d = tmp_path / "po"; d.mkdir()
    (d / "message.md").write_text("Plan: implement step 2 as briefed. Do you approve?")
    (d / "po-brief.md").write_text(BRIEF)
    _, r, _ = turn(world, po.MESSAGE, FAKE_PO_DIR=str(d))
    assert po.parse(r["result"]).kind == "approval"
    (d / "message.md").write_text('FAKE:reply={"kind": "continue"}')          # Task 13's directive path still wins
    assert turn(world, po.MESSAGE, FAKE_PO_DIR=str(d))[1]["result"] == '{"kind": "continue"}'
