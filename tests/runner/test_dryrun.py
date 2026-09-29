"""Task 24 (offline): the dry run's wiring — its arm configs, scripted owners and checklists, `orchestrate.dry_run()`
and `dry_report()` with run_arm/setup faked, the keychain never read on a dry pass, and `runner dry-run [--report]`.
The end-to-end dry run itself is tests/runner/test_dryrun_e2e.py (docker)."""
import json

import pytest

from runner import checklist, cli, config, credentials, docker, orchestrate, owner, paths, secrets, stepflow
from runner.config import Limits
from runner.docker import RunSpec
from runner.paths import Paths

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
    assert checklist.computed_ids(md) == {"setup.manifest-matches-pass1", "setup.agent-turns"}
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

def test_a_dry_pass_gathers_its_scan_literals_without_the_keychain(fake_orch, monkeypatch):
    seen = []
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: seen.append(k) or ["dry-run-dummy-token"])
    fake_orch.make("dryrun", pass_="dry7")
    orchestrate.run_arm("dry7", "dryrun", fake_orch.cred, fake_orch.owner)
    assert seen and all(k.get("keychain") is False for k in seen)


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


def test_the_report_passes_only_when_every_pass_proved_its_point(fake_dry):
    res = orchestrate.dry_run()
    out = orchestrate.dry_report(res)
    assert out == paths.RESULTS / "dryrun-validation.md" and out.read_text().rstrip().endswith("**Result: PASS**")
    for bad in ({**res, "dry2": {"completed": True}}, {**res, "dry3": {"completed": True}},
                {**res, "dry1": {"stopped_at": 4}}, {**res, "dry4": {"paused_after": 1}}):
        assert orchestrate.dry_report(bad).read_text().rstrip().endswith("**Result: FAIL**")


def test_the_report_fails_on_a_token_in_evidence_or_state_or_a_leftover_container(fake_dry, monkeypatch):
    res = orchestrate.dry_run()
    leak = paths.STATE / "dry2" / "x.log"; leak.write_text("token dry-run-dummy-token here\n")
    rep = orchestrate.dry_report(res).read_text()
    assert "secret findings (evidence + state, .gz decompressed): 1" in rep and rep.rstrip().endswith("FAIL**")
    leak.unlink()
    monkeypatch.setattr(docker, "running", lambda label="bakeoff.run": ["abc"])
    assert orchestrate.dry_report(res).read_text().rstrip().endswith("**Result: FAIL**")


def test_cli_dry_run_exits_1_unless_the_report_says_pass(fake_dry, monkeypatch, capsys):
    assert cli.main(["dry-run", "--report"]) == 0
    assert "PASS" in capsys.readouterr().out
    def failing(res):
        (paths.RESULTS / "r.md").write_text("**Result: FAIL**\n")
        return paths.RESULTS / "r.md"
    monkeypatch.setattr(orchestrate, "dry_report", failing)
    assert cli.main(["dry-run", "--report"]) == 1
    assert cli.main(["dry-run"]) == 0                                    # no report asked: the results, as JSON
