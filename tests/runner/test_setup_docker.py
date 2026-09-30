"""The setup flow against the real Docker daemon: the dry-run arm (fake claude, dummy credential), real egress
stage, real verify script (lib.sh). No model calls, no quota, fake PAT strings only. Opt in with --run-docker."""
import dataclasses, gzip, json, os, shutil, stat
import pytest
from runner import checklist, config, credentials, docker, faults, gitops
from runner.config import Smoke
from runner.docker import Mount
from runner.paths import Paths

pytestmark = pytest.mark.docker

PASS = "dry9"
FAKE_PAT = "github_pat_FAKE_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"   # fake only, never a real token

DRY_MD = """# dryrun (test copy; Task 24 writes the real one)
## Machine-verified
- `common.claude-version` — the pinned Claude Code
- `common.isolation-env` — auto-memory off, config dir
- `common.git-identity` — the neutral identity
- `common.no-foreign-plugins` — none
- `common.origin` — local bare origin, main resolves
- `common.no-foreign-model-ids` — host
- `setup.origin-push` — host
- (computed) `setup.manifest-created` — host, when the effective manifest list is not empty
- (computed) `setup.agent-turns` — host, when setup prompts are configured
## Owner-verified
- [ ] OV1: The setup session's reply reads sensibly.
## Known traps
- none
"""


class StubOwner:
    """Task 14's owner API (setup_reply, items, confirm), answering from a list; records what it was shown."""
    def __init__(self, replies=(), items_ok=True):
        self.replies, self.shown, self.items_ok = list(replies), [], items_ok

    def setup_reply(self, text):
        self.shown.append(text)
        return (self.replies.pop(0) if self.replies else ""), 1.5

    def items(self, items):
        return {i: (self.items_ok, "stub", 0.5) for i, _ in items}

    def confirm(self, text):
        return False


@pytest.fixture
def checks_dir(tmp_path, monkeypatch):
    d = tmp_path / "checklists"; (d / "verify").mkdir(parents=True)
    shutil.copy(checklist.CHECKS_DIR / "verify" / "lib.sh", d / "verify" / "lib.sh")
    (d / "verify" / "dryrun.sh").write_text('set -u; . /checks/lib.sh; common dryrun ""\n')
    (d / "dryrun.md").write_text(DRY_MD)
    monkeypatch.setattr(checklist, "CHECKS_DIR", d)
    return d


def use_arm(monkeypatch, **changes):
    arm = dataclasses.replace(config.load_arm("dryrun"), **changes)       # captured first (preflight M3)
    real = config.load_arm
    monkeypatch.setattr(config, "load_arm", lambda name: arm if name == "dryrun" else real(name))
    return arm


@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    assert not docker.running("bakeoff.run=dry9/dryrun") and not docker.running("bakeoff.run=pass1/control")
    assert not docker.sweep("bakeoff.run=dry9/dryrun")["networks"]


def test_setup_runs_shell_agent_turns_and_post_shell_then_is_green(tmp_state, checks_dir, monkeypatch):
    use_arm(monkeypatch, setup_shell=["printf shell > shell-was-here.txt"],
            setup_agent=["Principles:\n{principles}\nFAKE:reply=set up", "FAKE:reply=second"],
            setup_post_shell=["test -f shell-was-here.txt && printf post > post-was-here.txt"])
    owner = StubOwner(replies=["FAKE:reply=answered"])
    r = checklist.run_setup(PASS, "dryrun", credentials.dummy(), owner)
    p, out = Paths(PASS, "dryrun"), Paths(PASS, "dryrun").setup_results
    got = {c.id: c for c in r.checks}
    assert r.green, [c for c in r.checks if not c.ok]
    assert "setup.manifest-created" not in got         # dryrun lists no manifest paths: omitted (T10 FR1)
    for cid in ["common.claude-version", "common.isolation-env", "common.git-identity", "common.no-foreign-plugins",
                "common.origin", "common.no-foreign-model-ids", "setup.origin-push", "setup.agent-turns"]:
        assert got[cid].ok, got[cid]
    # the owner's reply went in as the next turn, before the second configured prompt
    assert owner.shown == ["set up", "answered", "second"]
    prompts = sorted((out / "turns").glob("setup-a1-*.prompt.md"))
    assert [f.read_text() for f in prompts][1:] == ["FAKE:reply=answered", "FAKE:reply=second"]
    assert config.CONFIG_DIR.joinpath("project-principles.md").read_text() in prompts[0].read_text()
    # M5: the setup session's transcripts are collected and pin-verified with their streams
    assert list((out / "transcripts").rglob("*.jsonl.gz"))
    pin = json.loads((out / "model-pin.json").read_text())
    assert pin["ok"] and pin["stream_assistant_messages"] == 3
    # shell logs, setup commit, origin pushed, records, snapshot
    assert "exit 0" in (out / "shell" / "01.log").read_text() and "exit 0" in (out / "shell" / "02.log").read_text()
    assert gitops.log(p, "HEAD~1", "HEAD")[0]["subject"] == "Set up fake claude (runner self-test) 0"
    assert gitops.git(p, "rev-parse", "origin/main").stdout == gitops.git(p, "rev-parse", "HEAD").stdout
    for f in ["checklist.json", "owner-checklist.json", "versions.json", "installed-commands.json",
              "model-overrides.json", "manifest.json", "egress.log", "setup-turns.json"]:
        assert (out / f).exists(), f
    assert json.loads((out / "versions.json").read_text())["owner_setup_seconds"] == 3 * 1.5 + 0.5
    assert {"shell-was-here.txt", "post-was-here.txt"} <= set(gitops.ls_files(p, "HEAD"))
    assert (p.snapshots / "step-01.tar").is_file()
    assert checklist.is_green(p)
    overrides = json.loads((out / "model-overrides.json").read_text())                    # FR1 item 4
    assert overrides["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == config.load_pins().model
    assert overrides["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == config.load_pins().model


def test_an_off_pin_model_in_a_setup_turn_is_a_harness_fault(tmp_state, checks_dir, monkeypatch):   # M5
    use_arm(monkeypatch, setup_agent=["FAKE:subagent_model=claude-sonnet-4-5-20250929\nFAKE:reply=ok"])
    with pytest.raises(faults.HarnessFault) as e:
        checklist.run_setup(PASS, "dryrun", credentials.dummy(), StubOwner())
    assert e.value.kind == "model-pin" and "claude-sonnet-4-5-20250929" in e.value.signature
    out = Paths(PASS, "dryrun").setup_results
    assert not json.loads((out / "model-pin.json").read_text())["ok"]
    assert not (out / "checklist.json").exists()                  # never recorded as a setup result


def test_the_smoke_turn_runs_outside_the_repo_and_its_transcripts_leave_the_arm_home(tmp_state, checks_dir,
                                                                                      monkeypatch):
    use_arm(monkeypatch, smoke=Smoke("FAKE:reply=I would brainstorm", "brainstorming"))
    (checks_dir / "dryrun.md").write_text(DRY_MD.replace("## Owner-verified",
                                                         "- `dryrun.smoke` — skill invoked\n## Owner-verified"))
    r = checklist.run_setup(PASS, "dryrun", credentials.dummy(), StubOwner())
    p, out = Paths(PASS, "dryrun"), Paths(PASS, "dryrun").setup_results
    smoke = {c.id: c for c in r.checks}["dryrun.smoke"]
    assert not smoke.ok and not r.green                            # the fake never calls the Skill tool
    moved = list((out / "smoke" / "transcripts").rglob("*.jsonl.gz"))
    assert moved and all("-work-smoke" in str(f) for f in moved)
    assert json.loads((out / "smoke" / "model-pin.json").read_text())["ok"]
    assert not list((p.config_dir / "projects").rglob("*.jsonl"))  # moved, not copied, out of the arm's home
    assert not (p.work / "smoke").exists()


def test_the_pat_is_readable_by_gh_in_the_container_and_gh_repo_is_set(tmp_state, monkeypatch):   # M4, 0600
    p = Paths("pass1", "control"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    monkeypatch.setattr(checklist.credentials, "github_pat", lambda pass_, arm: FAKE_PAT)
    assert checklist._install_github_pat(p, config.load_arm("control"), "pass1")
    assert stat.S_IMODE(os.lstat(p.home / ".config/gh/hosts.yml").st_mode) == 0o600
    s = dataclasses.replace(checklist.arm_spec(p, config.load_arm("control"), [
        "bash", "-c", 'printf "%s|%s" "$(gh auth token --hostname github.com)" "$GH_REPO"']),
        image=config.load_pins().images["dryrun"])
    r = docker.run(s, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.decode() == f"{FAKE_PAT}|troupe-run/bakeoff-specs-control-pass1"


def test_the_origin_checks_pass_on_the_local_bare_origin_and_fail_elsewhere(tmp_state, checks_dir):
    from runner import repo
    p = Paths(PASS, "dryrun"); repo.init(p, "dryrun", PASS)
    ok = {c.id: c for c in checklist.verify(p, config.load_arm("dryrun"), "setup")}
    assert checklist._origin_push(p).ok
    assert ok["common.origin"].ok and ok["common.git-identity"].ok and ok["common.claude-version"].ok
    gitops.git(p, "remote", "set-url", "origin", "/tmp/elsewhere.git", write=True)
    bad = {c.id: c for c in checklist.verify(p, config.load_arm("dryrun"), "setup")}
    assert not bad["common.origin"].ok and "/tmp/elsewhere.git" in bad["common.origin"].detail
    assert not checklist._origin_push(p).ok                        # setup.origin-push fails with it too


# --- fix round 1 ----------------------------------------------------------------------------------------
def test_a_setup_prompt_whose_last_turn_failed_is_not_green(tmp_state, checks_dir, monkeypatch):   # FR1 item 2
    use_arm(monkeypatch, setup_agent=["FAKE:is_error\nFAKE:reply=broke"])
    r = checklist.run_setup(PASS, "dryrun", credentials.dummy(), StubOwner())
    c = {c.id: c for c in r.checks}["setup.agent-turns"]
    assert not c.ok and "is_error" in c.detail and not r.green


def test_a_missing_manifest_path_is_named_by_a_failing_check(tmp_state, checks_dir, monkeypatch):   # FR1 item 7
    use_arm(monkeypatch, manifest_paths=["nope-not-created"])
    r = checklist.run_setup(PASS, "dryrun", credentials.dummy(), StubOwner())
    c = {c.id: c for c in r.checks}["setup.manifest-created"]
    assert not c.ok and "nope-not-created" in c.detail and not r.green


def test_checklist_after_a_shell_session_is_a_full_recheck(tmp_state, checks_dir, monkeypatch):     # FR1 item 3
    use_arm(monkeypatch, setup_agent=["FAKE:reply=set up"])
    assert checklist.run_setup(PASS, "dryrun", credentials.dummy(), StubOwner()).green
    p = Paths(PASS, "dryrun")
    snap_before = (p.snapshots / "step-01.tar").stat().st_mtime_ns
    checklist.mark_dirty(p, "test: owner shell")
    (p.repo / "owner-edit.txt").write_text("edited in the shell\n")                  # what a shell session did
    with pytest.raises(checklist.NotReady, match="dirty"):
        checklist.require_clean_green(p)
    r = checklist.recheck(PASS, "dryrun", None)
    assert r.green and not checklist.is_dirty(p)
    checklist.require_clean_green(p)
    assert "owner-edit.txt" in gitops.ls_files(p, "HEAD")                                 # committed and pushed
    assert gitops.git(p, "rev-parse", "origin/main").stdout == gitops.git(p, "rev-parse", "HEAD").stdout
    rec = {c["id"]: c for c in json.loads((p.setup_results / "checklist.json").read_text())}
    assert rec["setup.agent-turns"]["ok"] and rec["common.origin"]["ok"]                  # carried over + re-run
    assert (p.snapshots / "step-01.tar").stat().st_mtime_ns > snap_before
    # a recheck that is not green leaves setup dirty and says so
    checklist.mark_dirty(p, "test: owner shell")
    gitops.git(p, "remote", "set-url", "origin", "/tmp/elsewhere.git", write=True)
    bad = checklist.recheck(PASS, "dryrun", None)
    assert not bad.green and checklist.is_dirty(p) and not checklist.is_green(p)
    rec = {c["id"]: c for c in json.loads((p.setup_results / "checklist.json").read_text())}
    assert not rec["common.origin"]["ok"]
