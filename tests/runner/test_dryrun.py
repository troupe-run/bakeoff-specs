"""Task 24 (offline): the dry run's wiring — its arm configs, scripted owners and checklists, `orchestrate.dry_run()`
and `dry_report()` with run_arm/setup faked, the keychain never read on a dry pass, and `runner dry-run [--report]`.
The end-to-end dry run itself is tests/runner/test_dryrun_e2e.py (docker)."""
import json

import pytest

from runner import checklist, cli, config, credentials, docker, orchestrate, owner, paths, secrets, stepflow
from runner.config import Limits
from runner.docker import RunSpec
from runner.paths import Paths

REAL_LITERALS = secrets.literals                                      # before any fixture fakes it
DRY_ARMS = ("dryrun", "dryrun-broken", "dryrun-pinfault", "dryrun-edge")


# ---- configs, scripted owners, checklists ---------------------------------------------------------------------

def test_the_four_dry_arms_differ_only_in_name_repo_and_env():
    base = config.load_arm("dryrun")
    assert base.dry and base.tracker == "dry" and base.must_run == ["/dry-close"] and base.entry == "{handoff}"
    assert "dry-next.md" in base.setup_shell[0] and "dry-close.md" in base.setup_shell[0]
    envs = {}
    for name in DRY_ARMS:
        a = config.load_arm(name)
        assert a.repo_name == f"bakeoff-specs-{name}"
        envs[name] = a.env
        assert {**vars(a), "name": "", "repo_name": "", "env": {}} == {**vars(base), "name": "", "repo_name": "", "env": {}}
    assert envs == {"dryrun": {}, "dryrun-broken": {"FAKE_VARIANT": "broken"},
                    "dryrun-pinfault": {"FAKE_SUBAGENT_MODEL": "claude-haiku-4-5"}, "dryrun-edge": {"FAKE_VARIANT": "edge"}}
    assert not any(n.startswith("dryrun") for n in config.all_arms())          # never a real arm


@pytest.mark.parametrize("name", DRY_ARMS)
def test_every_dry_arm_has_a_checklist_whose_listed_checks_are_all_produced(name):
    arm = config.load_arm(name)
    md = (checklist.CHECKS_DIR / f"{name}.md").read_text()
    common = {"common.claude-version", "common.isolation-env", "common.git-identity", "common.no-foreign-plugins",
              "common.origin"}
    produced = common | checklist.host_check_ids(arm)                  # the verify script's + the host checks
    assert checklist.missing_checks(md, [checklist.Check(i, True, "") for i in produced], produced) == []
    assert common | {"common.no-foreign-model-ids", "setup.origin-push"} <= checklist.machine_ids(md)
    assert checklist.computed_ids(md) == {"setup.manifest-created", "setup.agent-turns"}
    assert checklist.owner_items(md) == [("OV1", "dry run (scripted owner).")]
    sh = (checklist.CHECKS_DIR / "verify" / f"{name}.sh").read_text()
    assert ('common dryrun ""' in sh) if name == "dryrun" else ('exec bash /checks/dryrun.sh "$@"' in sh)


def test_the_scripted_owners_answer_as_the_dry_run_needs():
    arm = config.load_arm("dryrun")
    o = owner.ScriptedOwner(config.CONFIG_DIR / "dryrun-owner.toml").bind(arm)
    assert o.escalation("q", "c") == ("Print floats exactly as written in the file.", 0.0)
    assert o.confirm("x") is True and o.reclassify("turn_seconds", "") == "arm"
    assert o.items([("Q1", "t")]) == {"Q1": (True, "scripted", 0.0)}
    assert o.step_review("# Step 1 summary — dryrun (dry1)") == ("continue", 0.0)
    o4 = owner.ScriptedOwner(config.CONFIG_DIR / "dryrun-owner-dry4.toml").bind(config.load_arm("dryrun-edge"))
    assert o4.step_review("# Step 1 summary — dryrun-edge (dry4)") == ("pause", 0.0)
    assert o4.step_review("# Step 1 summary — dryrun-edge (dry4)") == ("continue", 0.0)      # once: then resumed
    assert o4.step_review("# Step 2 summary — dryrun-edge (dry4)") == ("continue", 0.0)


def test_the_dry_passes_are_the_four_of_the_brief():
    assert [(p, a, s) for p, a, s, _ in orchestrate.DRY] == [
        ("dry1", "dryrun", "dryrun-owner.toml"), ("dry2", "dryrun-broken", "dryrun-owner.toml"),
        ("dry3", "dryrun-pinfault", "dryrun-owner.toml"), ("dry4", "dryrun-edge", "dryrun-owner-dry4.toml")]
    limits = {k for _, _, _, lim in orchestrate.DRY for k in lim}
    assert limits <= set(Limits.__dataclass_fields__)
    assert orchestrate.DRY[3][3]["turn_seconds"] == 20


# ---- the keychain is never read on a dry pass -------------------------------------------------------------------

def test_a_dry_pass_never_reads_the_keychain(fake_orch, monkeypatch):
    def keychain(*a, **k):
        raise AssertionError("a dry pass read the keychain")
    monkeypatch.setattr(secrets, "literals", REAL_LITERALS)             # fake_orch fakes it: the real one here
    monkeypatch.setattr(credentials, "from_keychain", keychain)
    monkeypatch.setattr(credentials, "github_pat", keychain)
    monkeypatch.setattr(secrets, "keychain_pat", keychain)
    monkeypatch.setattr(secrets, "_KEYCHAIN", {})                        # nothing cached from another test
    fake_orch.make("dryrun", pass_="dry7")
    res = orchestrate.run_arm("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    assert res == {"completed": True}


def test_a_real_pass_still_gathers_keychain_literals(fake_orch, monkeypatch):
    seen = []
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: seen.append(k) or ["x"])
    fake_orch.make("control", pass_="pass1")
    f = paths.RESULTS / "pass1" / "order.json"; f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"seed": 1, "rule": "t", "order": ["control"]}))
    orchestrate.run_pass("pass1", fake_orch.cred, fake_orch.owner)
    assert seen and seen[0].get("keychain", True) is True


# ---- dry_run / dry_report (setup and run_arm faked) ---------------------------------------------------------------

def spec(env):
    return RunSpec("n", "img", "l", "none", [], env, "/", ["true"], False, config.load_pins().limits, False)


@pytest.fixture
def fake_dry(tmp_state, monkeypatch):
    calls, green = [], {"ok": True}

    class R:
        def __init__(self): self.green, self.checks = green["ok"], []

    def setup(pass_, arm, cred, o, again=False):
        assert isinstance(o, owner.ScriptedOwner) and cred._dummy
        calls.append(("setup", pass_, arm, o.s["review"].get("pause_after", [])))
        (paths.STATE / pass_ / arm).mkdir(parents=True, exist_ok=True)
        return R()

    runs: dict = {}

    def run_arm(pass_, arm, cred, o, limits_override=None, stop_after=None):
        calls.append(("run_arm", pass_, arm, tuple(sorted(limits_override))))
        docker.run_argv(spec({"A": "b"}))                               # a container spec, recorded
        assert paths.brief_path(pass_).read_text() == (paths.REPO_ROOT / "scenario" / "po-brief.md").read_text()
        if pass_ == "dry3":
            raise stepflow.Halt("same harness fault twice")
        if pass_ == "dry2":
            return {"stopped_at": 2}
        if pass_ == "dry4":                                              # paused after step 1, then resumed
            runs["dry4"] = not runs.get("dry4")
            return {"paused_after": 1} if runs["dry4"] else {"completed": True}
        return {"completed": True}

    monkeypatch.setattr(orchestrate, "setup", setup)
    monkeypatch.setattr(orchestrate, "run_arm", run_arm)
    monkeypatch.setattr(docker, "running", lambda label="bakeoff.run": [])
    return calls, green


def test_dry_run_sets_up_and_runs_the_four_passes_from_nothing_and_resumes_dry4(fake_dry):
    calls, _ = fake_dry
    stale = paths.RESULTS / "dry1" / "old.txt"; stale.parent.mkdir(parents=True); stale.write_text("x")
    res = orchestrate.dry_run()
    assert res == {"dry1": {"completed": True}, "dry2": {"stopped_at": 2}, "dry3": {"halted": "same harness fault twice"},
                   "dry4": {"completed": True}}
    assert not stale.exists()                                           # every pass starts from nothing
    assert [c[:3] for c in calls if c[0] == "run_arm"] == [("run_arm", "dry1", "dryrun"), ("run_arm", "dry2", "dryrun-broken"),
                                                            ("run_arm", "dry3", "dryrun-pinfault"),
                                                            ("run_arm", "dry4", "dryrun-edge"), ("run_arm", "dry4", "dryrun-edge")]
    assert ("setup", "dry4", "dryrun-edge", [1]) in calls
    assert json.loads((Paths("dry4", "dryrun-edge").results / "resume.json").read_text()) == {"paused_after": 1}
    assert json.loads((paths.RESULTS / "dryrun-specs.json").read_text()) == {"specs": 5, "specs_containing_token": 0}


def test_a_container_spec_carrying_the_token_is_counted(fake_dry, monkeypatch):
    real = orchestrate.run_arm

    def leaky(*a, **k):
        docker.run_argv(spec({"X": credentials.dummy().raw_for_scanner()}))
        return real(*a, **k)
    monkeypatch.setattr(orchestrate, "run_arm", leaky)
    orchestrate.dry_run()
    assert json.loads((paths.RESULTS / "dryrun-specs.json").read_text())["specs_containing_token"] == 5


def test_a_setup_that_is_not_green_is_a_failed_pass_not_a_run(fake_dry):
    calls, green = fake_dry
    green["ok"] = False
    res = orchestrate.dry_run()
    assert all("setup_not_green" in r for r in res.values()) and not [c for c in calls if c[0] == "run_arm"]


# ---- dry_report gates on what each pass proves (fix round 1): faked evidence, no docker ----------------------------

EXPECTED = {1: 101, 2: 109, 3: 121, 4: 135, 5: 146, 6: 151, 7: 161}
RES = {"dry1": {"completed": True}, "dry2": {"stopped_at": 2}, "dry3": {"halted": "x"}, "dry4": {"completed": True}}


def W(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj))


def evidence():
    """A faked evidence tree for which every gate holds (the shapes the real runner writes)."""
    r, s = paths.RESULTS, paths.STATE
    d1 = r / "dry1" / "dryrun"
    for n, total in EXPECTED.items():
        W(d1 / f"{n:02d}" / "hidden" / "summary.json",
          {"total": total, "passed": total, "failed": 0, "flaky": 0, "flaky_arm": 0, "tests": {}})
        W(d1 / f"{n:02d}" / "git.json", {"sha_before": f"s{n}", "sha_after": f"s{n + 1}"})
        W(d1 / f"{n:02d}" / "a" / "discovery.json", {"sha_before": f"s{n}", "discovery": {"why": "approval"}})
        for pin in (d1 / f"{n:02d}" / "model-pin.json", d1 / f"{n:02d}" / "a" / "model-pin.json"):
            W(pin, {"ok": True, "violations": [], "assistant_messages": 3})
    W(d1 / "02" / "hand-edit" / "probe.json",
      {"env_default": True, "flag_wins": True, "unchanged_without_env": True, "installed": True})
    W(r / "dry2" / "dryrun-broken" / "arm-result.json", {"stopped_at": 2, "reason": "no progress in 3 attempts"})
    W(r / "dry3" / "faults.jsonl", "".join(json.dumps({"kind": "model-pin", "signature": "claude-haiku-4-5",
                                                       "action": a, "detail": f"{paths.REPO_ROOT}/results/x"}) + "\n"
                                           for a in ("rerun", "halt")))
    W(r / "dry3" / "HALTED", "{}")
    d4 = r / "dry4" / "dryrun-edge"
    W(d4 / "01" / "run.json", {"interventions": ["transient-retry:API Error:  overloaded"]})
    W(d4 / "breaches.json", [{"step": 2, "breach": "turn_seconds", "owner": "arm"}])
    W(d4 / "resume.json", {"paused_after": 1})
    W(s / "dry4" / "dryrun-edge" / "progress.json", {"steps": {"1": {"review": "pause"}, "7": {"review": "continue"}}})
    W(r / "dry4" / "run-log.jsonl", "".join(json.dumps({"event": "run-ended", "step": n, "run": x}) + "\n"
                                             for n in range(1, 8) for x in ("a", "b")))
    W(r / "dryrun-specs.json", {"specs": 865, "specs_containing_token": 0})
    W(d1.parent / "dryrun" / "arm-result.json", {"completed": True, "last_step": 7})
    W(d4 / "arm-result.json", {"completed": True, "last_step": 7})


@pytest.fixture
def ev(tmp_state, monkeypatch):
    monkeypatch.setattr(docker, "running", lambda label="bakeoff.run": [])
    evidence()


def report(res=RES):
    return orchestrate.dry_report(res).read_text()


def test_the_report_passes_on_complete_evidence_and_says_why(ev):
    rep = report()
    assert rep.rstrip().endswith("**Result: PASS**")
    for fact in ("dry1 hidden counts", "dry1 N.a/N.b sha_before", "dry1 hand-edit probe", "dry1 model pin",
                 "dry2 stop rule", "dry3 halt rule", "dry4 transient retry", "dry4 timeout owned by the arm",
                 "dry4 pause and resume"):
        assert f"- ok: {fact}" in rep, fact


def _set(rel, key, value):
    f = paths.RESULTS / rel
    o = json.loads(f.read_text()); o[key] = value; f.write_text(json.dumps(o))


BREAKERS = {
    "dry1 hidden counts": lambda: _set("dry1/dryrun/04/hidden/summary.json", "passed", 134),
    "dry1 hidden counts (failed)": lambda: _set("dry1/dryrun/07/hidden/summary.json", "failed", 1),
    "dry1 hidden counts (total)": lambda: _set("dry1/dryrun/01/hidden/summary.json", "total", 100),
    "dry1 N.a/N.b sha_before": lambda: _set("dry1/dryrun/03/a/discovery.json", "sha_before", "other"),
    "dry1 hand-edit probe": lambda: _set("dry1/dryrun/02/hand-edit/probe.json", "flag_wins", False),
    "dry1 model pin": lambda: _set("dry1/dryrun/05/a/model-pin.json", "violations", [{"model": "x"}]),
    "dry1 model pin (not ok)": lambda: _set("dry1/dryrun/06/model-pin.json", "ok", False),
    "dry2 stop rule": lambda: _set("dry2/dryrun-broken/arm-result.json", "reason", "harness"),
    "dry2 stop rule (step)": lambda: _set("dry2/dryrun-broken/arm-result.json", "stopped_at", 3),
    "dry3 halt rule": lambda: W(paths.RESULTS / "dry3" / "faults.jsonl", json.dumps(
        {"kind": "model-pin", "signature": "claude-haiku-4-5", "action": "halt"}) + "\n"),
    "dry3 halt rule (other fault)": lambda: W(paths.RESULTS / "dry3" / "faults.jsonl", "".join(json.dumps(
        {"kind": "infra-container", "signature": "x", "action": a}) + "\n" for a in ("rerun", "halt"))),
    "dry4 transient retry": lambda: _set("dry4/dryrun-edge/01/run.json", "interventions", []),
    "dry4 timeout owned by the arm": lambda: W(paths.RESULTS / "dry4/dryrun-edge/breaches.json",
                                               [{"step": 2, "breach": "turn_seconds", "owner": "harness"}]),
    "dry4 pause and resume (review)": lambda: W(paths.STATE / "dry4/dryrun-edge/progress.json",
                                                {"steps": {"1": {"review": "continue"}}}),
    "dry4 pause and resume (1.b twice)": lambda: (paths.RESULTS / "dry4/run-log.jsonl").open("a").write(
        json.dumps({"event": "run-ended", "step": 1, "run": "b"}) + "\n"),
    "dry4 pause and resume (no resume record)": lambda: (paths.RESULTS / "dry4/dryrun-edge/resume.json").unlink(),
}


@pytest.mark.parametrize("fact", sorted(BREAKERS))
def test_each_gate_fails_the_report_when_its_fact_is_wrong(ev, fact):
    BREAKERS[fact]()
    rep = report()
    assert rep.rstrip().endswith("**Result: FAIL**"), fact
    assert f"- FAIL: {fact.split(' (')[0]}" in rep


@pytest.mark.parametrize("bad", [{**RES, "dry2": {"completed": True}}, {**RES, "dry3": {"completed": True}},
                                 {**RES, "dry1": {"stopped_at": 4}}, {**RES, "dry4": {"paused_after": 1}}])
def test_the_report_fails_when_a_pass_ended_the_wrong_way(ev, bad):
    assert report(bad).rstrip().endswith("**Result: FAIL**")


def test_the_report_fails_on_a_token_in_evidence_or_state_or_a_leftover_container(ev, monkeypatch):
    leak = paths.STATE / "dry2" / "x.log"; W(leak, "token dry-run-dummy-token here\n")
    rep = report()
    assert "secret findings (evidence + state, .gz decompressed): 1" in rep and rep.rstrip().endswith("FAIL**")
    leak.unlink()
    monkeypatch.setattr(docker, "running", lambda label="bakeoff.run": ["abc"])
    assert report().rstrip().endswith("**Result: FAIL**")


def test_the_committed_report_carries_no_host_paths(ev):
    res = {**RES, "dry3": {"halted": f"same fault: {paths.REPO_ROOT}/results/dry3/x.jsonl.gz"}}
    rep = report(res)
    assert str(paths.REPO_ROOT) not in rep and "results/dry3/x.jsonl.gz" in rep


def test_the_report_can_be_regenerated_from_existing_evidence(ev, capsys):
    assert orchestrate.dry_results() == RES | {"dry3": {"halted": "{}"}}
    assert cli.main(["dry-run", "--report-only"]) == 0
    assert (paths.RESULTS / "dryrun-validation.md").read_text().rstrip().endswith("**Result: PASS**")
    _set("dry2/dryrun-broken/arm-result.json", "stopped_at", 3)
    assert cli.main(["dry-run", "--report-only"]) == 1


# ---- dry_run: a halt during setup, a pause reported as paused_at, no keychain -----------------------------------

def test_a_halt_during_setup_is_that_passs_result_and_the_run_goes_on(fake_dry, monkeypatch):
    real = orchestrate.setup

    def halting(pass_, arm, cred, o, again=False):
        if pass_ == "dry2":
            raise stepflow.Halt("setup fault twice")
        return real(pass_, arm, cred, o, again)
    monkeypatch.setattr(orchestrate, "setup", halting)
    res = orchestrate.dry_run()
    assert res["dry2"] == {"halted": "setup fault twice"} and res["dry4"] == {"completed": True}


def test_a_pause_reported_as_paused_at_is_resumed_too(fake_dry, monkeypatch):
    real, seen = orchestrate.run_arm, {}

    def at(pass_, *a, **k):
        if pass_ == "dry1" and not seen:
            seen["x"] = 1
            return {"paused_at": 3}
        return real(pass_, *a, **k)
    monkeypatch.setattr(orchestrate, "run_arm", at)
    assert orchestrate.dry_run()["dry1"] == {"completed": True}
    assert json.loads((Paths("dry1", "dryrun").results / "resume.json").read_text()) == {"paused_at": 3}


def test_cli_dry_run_exits_1_unless_the_report_says_pass(ev, monkeypatch, capsys):
    monkeypatch.setattr(orchestrate, "dry_run", lambda: dict(RES))       # the passes' evidence is faked (ev)
    assert cli.main(["dry-run", "--report"]) == 0
    assert "PASS" in capsys.readouterr().out
    def failing(res):
        (paths.RESULTS / "r.md").write_text("**Result: FAIL**\n")
        return paths.RESULTS / "r.md"
    monkeypatch.setattr(orchestrate, "dry_report", failing)
    assert cli.main(["dry-run", "--report"]) == 1
    assert cli.main(["dry-run"]) == 0                                    # no report asked: the results, as JSON
