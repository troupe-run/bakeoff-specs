# tests/runner/test_checklist.py
import gzip, json, os, stat, subprocess
import pytest
from runner import checklist, config, credentials, docker, transcripts
from runner.paths import Paths

MD = """# x
## Machine-verified
- `common.claude-version` — a
## Owner-verified
- [ ] OV1: The constitution reads as this project's principles.
- [ ] OV2: No warnings.
## Known traps
- none
"""

def test_green_needs_every_machine_check_and_every_owner_item():
    assert checklist.green([checklist.Check("a", True, "")], {"OV1": True})
    assert not checklist.green([checklist.Check("a", False, "")], {"OV1": True})
    assert not checklist.green([checklist.Check("a", True, "")], {"OV1": False})

def test_owner_items_are_parsed_in_order():
    assert checklist.owner_items(MD) == [("OV1", "The constitution reads as this project's principles."), ("OV2", "No warnings.")]

def test_manifest_diff_names_changed_added_and_removed_files():
    assert checklist.manifest_diff({"a": "1", "b": "2"}, {"a": "1", "b": "3", "c": "4"}) == ["b (changed)", "c (added)"]
    assert checklist.manifest_diff({"a": "1"}, {}) == ["a (removed)"]

def test_foreign_model_ids_are_caught_at_setup():                             # review F-6 / OD2
    c = checklist.model_ids_check([{"file": "agents/r.md", "model": "haiku"},
                                   {"file": "agents/x.md", "model": "claude-sonnet-4-5-20250929"}], ["claude-opus-5-5"])
    assert not c.ok and "claude-sonnet-4-5-20250929" in c.detail and "haiku" not in c.detail

def test_gh_hosts_file_holds_the_pat_for_github_com_only():
    y = checklist.gh_hosts_yml("github_pat_X")
    assert y.startswith("github.com:\n") and "oauth_token: github_pat_X" in y and "git_protocol: https" in y

def test_is_green_reads_both_records(tmp_state):
    p = Paths("pass1", "control"); d = p.setup_results; d.mkdir(parents=True)
    (d / "checklist.json").write_text(json.dumps([{"id": "a", "ok": True, "detail": ""}]))
    (d / "owner-checklist.json").write_text(json.dumps({"OV1": {"ok": True, "note": ""}}))
    assert checklist.is_green(p)
    (d / "owner-checklist.json").write_text(json.dumps({"OV1": {"ok": False, "note": "no"}}))
    assert not checklist.is_green(p)


# --- preflight rulings and hardening beyond the plan text ------------------------------------------------
FAKE_PAT = "github_pat_FAKE_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"   # fake only, never a real token


def test_every_arm_including_dry_ones_has_the_origin_push_host_check():         # preflight B4
    assert "dryrun" in checklist.HOST_CHECKS
    for arm, ids in checklist.HOST_CHECKS.items():
        assert {"setup.origin-push", "common.no-foreign-model-ids", "setup.manifest-matches-pass1"} <= ids, arm


def test_host_check_ids_follow_the_plan_for_real_arms():
    h = checklist.HOST_CHECKS
    assert "github.issues-access" in h["control"] and "github.issues-access" not in h["speckitty"]
    assert "github.issues-access" not in h["dryrun"]
    assert "superpowers.smoke" in h["superpowers"] and "openspec.entry-commands" in h["openspec"]
    assert "control.entry-commands" not in h["control"]


def test_lib_sh_names_the_origin_check():                                      # preflight B4
    lib = (checklist.CHECKS_DIR / "verify" / "lib.sh").read_text()
    assert "check common.origin " in lib


@pytest.mark.parametrize("pass_,arm,want", [("pass1", "control", "troupe-run/bakeoff-specs-control-pass1"),
                                            ("pass2", "openspec", "troupe-run/bakeoff-specs-openspec"),
                                            ("pass1", "speckitty", None), ("dry9", "control", None),
                                            ("pass1", "dryrun", None)])
def test_setup_containers_get_gh_repo_only_for_github_arms_with_a_repo(pass_, arm, want):   # preflight M4
    s = checklist.arm_spec(Paths(pass_, arm), config.load_arm(arm), ["true"])
    assert s.env.get("GH_REPO") == want


def test_verify_containers_get_the_expected_values_from_the_pins(tmp_state):   # single source (pins, gitops)
    from runner import gitops
    s = checklist.arm_spec(Paths("dry9", "dryrun"), config.load_arm("dryrun"), ["true"])
    assert s.env["BK_EXPECT_CLAUDE_VERSION"] == f"{config.load_pins().claude_version} (Claude Code)"
    assert s.env["BK_EXPECT_ORIGIN"] == gitops.ORIGIN and s.env["BK_EXPECT_GIT_NAME"] == gitops.IDENTITY[0]
    assert s.network == "none" and all(m.ro for m in s.mounts)


def test_the_github_pat_is_installed_right_after_repo_init(tmp_state, monkeypatch):    # preflight M4 (order)
    calls = []
    monkeypatch.setattr(checklist, "_refuse_parked", lambda arm: None)
    monkeypatch.setattr(checklist, "_read_md", lambda arm: MD)
    monkeypatch.setattr(checklist.repo, "init", lambda p, a, s: calls.append("init") or p.config_dir.mkdir(parents=True))
    monkeypatch.setattr(checklist, "_install_github_pat", lambda p, a, s: calls.append("pat"))

    class Stage:
        net = "n"
        def __init__(self, *a): calls.append("stage")
        def __enter__(self): return self
        def __exit__(self, *e): pass
    monkeypatch.setattr(checklist.egress, "Stage", Stage)
    monkeypatch.setattr(checklist, "install_plugins", lambda *a: calls.append("plugins") or {})
    monkeypatch.setattr(checklist, "_shell", lambda *a: calls.append("shell") or 0)
    monkeypatch.setattr(checklist, "_agent_turns", lambda *a: calls.append("agent") or (0.0, {}))

    class Stop(Exception):
        pass
    monkeypatch.setattr(checklist.transcripts, "snapshot", lambda d: (_ for _ in ()).throw(Stop()))
    arm = config.load_arm("control")
    import dataclasses
    arm = dataclasses.replace(arm, setup_shell=["x"], setup_agent=["y"])
    monkeypatch.setattr(checklist.config, "load_arm", lambda name: arm)
    with pytest.raises(Stop):
        checklist.run_setup("pass1", "control", credentials.dummy(), object())
    assert calls[:3] == ["init", "pat", "stage"]


def _no_chmod(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("PAT files must be created 0600, never chmodded afterwards")
    monkeypatch.setattr(os, "chmod", refuse)
    monkeypatch.setattr(os, "fchmod", refuse)


def test_pat_files_are_created_0600_from_the_start(tmp_state, tmp_path, monkeypatch):   # Task 5 note / M4
    p = Paths("pass1", "control"); p.config_dir.mkdir(parents=True)
    asked = []
    monkeypatch.setattr(checklist.credentials, "github_pat", lambda pass_, arm: asked.append((pass_, arm)) or FAKE_PAT)
    mcp = tmp_path / "mcp"; mcp.mkdir()
    (mcp / "control.json").write_text('{"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}"}}')
    monkeypatch.setattr(checklist, "MCP_DIR", mcp)
    _no_chmod(monkeypatch)
    old = os.umask(0)
    try:
        assert checklist._install_github_pat(p, config.load_arm("control"), "pass1") is True
    finally:
        os.umask(old)
    hosts = p.home / ".config" / "gh" / "hosts.yml"
    for f in (hosts, p.home / ".bk-mcp.json"):
        assert stat.S_IMODE(os.lstat(f).st_mode) == 0o600, f
    assert hosts.read_text() == checklist.gh_hosts_yml(FAKE_PAT)
    assert json.loads((p.home / ".bk-mcp.json").read_text())["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == FAKE_PAT
    assert asked == [("pass1", "control")]
    assert not (p.results).exists()                       # never under results/ (Task 21 scans there)


def test_a_pat_file_that_already_exists_is_refused_not_overwritten(tmp_state, monkeypatch):
    p = Paths("pass1", "control"); p.config_dir.mkdir(parents=True)
    gh = p.home / ".config" / "gh"; gh.mkdir(parents=True)
    os.symlink("/tmp/elsewhere", gh / "hosts.yml")
    monkeypatch.setattr(checklist.credentials, "github_pat", lambda pass_, arm: FAKE_PAT)
    with pytest.raises(FileExistsError):
        checklist._install_github_pat(p, config.load_arm("control"), "pass1")


@pytest.mark.parametrize("pass_,arm", [("pass1", "speckitty"), ("dry9", "control"), ("dry9", "dryrun")])
def test_no_pat_for_beads_dry_arms_or_passes_without_a_github_repo(tmp_state, monkeypatch, pass_, arm):
    p = Paths(pass_, arm); p.config_dir.mkdir(parents=True)
    monkeypatch.setattr(checklist.credentials, "github_pat",
                        lambda *a: (_ for _ in ()).throw(AssertionError("keychain must not be read")))
    assert checklist._install_github_pat(p, config.load_arm(arm), pass_) is False
    assert not (p.home / ".config").exists()


def test_github_pat_reads_the_per_pass_arm_keychain_item_without_leaking(monkeypatch):
    seen = []
    def fake(argv, **k):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, FAKE_PAT + "\n", "")
    monkeypatch.setattr(credentials.subprocess, "run", fake)
    assert credentials.github_pat("pass1", "control") == FAKE_PAT
    assert seen[0][:4] == [credentials.SECURITY, "find-generic-password", "-s", "bakeoff-gh-pass1-control"]
    monkeypatch.setattr(credentials.subprocess, "run",
                        lambda argv, **k: subprocess.CompletedProcess(argv, 44, FAKE_PAT, "not found"))
    with pytest.raises(RuntimeError) as e:
        credentials.github_pat("pass1", "control")
    assert FAKE_PAT not in str(e.value) and "github-plan" in str(e.value)


def test_a_parked_arm_refuses_setup_before_anything_is_created(tmp_state):     # bmad PARKED: read the lock
    with pytest.raises(checklist.NotReady, match="bmad"):
        checklist.run_setup("dry9", "bmad", credentials.dummy(), object())
    assert not Paths("dry9", "bmad").base.exists()


def _stream(tmp_path, events):
    f = tmp_path / "s.stream.jsonl.gz"
    with gzip.open(f, "wt") as fh:
        for e in events:
            fh.write((e if isinstance(e, str) else json.dumps(e)) + "\n")
    return f


def test_invoked_skills_reads_skill_tool_uses_from_the_runner_stream(tmp_path):   # preflight m10 (shared helper)
    f = _stream(tmp_path, [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Skill brainstorming"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill",
                                                        "input": {"skill": "superpowers:brainstorming"}}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"skill": "x"}}]}},
        {"type": "assistant", "message": "not-a-dict"}, {"type": "assistant", "message": {"content": [1, None]}},
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "inp',
    ])
    assert transcripts.invoked_skills(f) == {"superpowers:brainstorming"}
    assert transcripts.invoked_skills(None) == set()


def test_smoke_matches_a_namespaced_or_bare_skill_name():
    assert checklist.skill_matches({"superpowers:brainstorming"}, "brainstorming")
    assert checklist.skill_matches({"brainstorming"}, "brainstorming")
    assert not checklist.skill_matches({"superpowers:brainstorming-extra"}, "brainstorming")


def _cp(stdout: str, rc: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess([], rc, stdout.encode(), stderr.encode())


def test_verify_output_is_parsed_defensively():
    good = '{"id": "a.x", "ok": true, "detail": "d"}\n'
    assert checklist.parse_verify("a", _cp(good)) == [checklist.Check("a.x", True, "d")]
    bad = checklist.parse_verify("a", _cp(good + '{"id": 1}\n{not json\nnoise\n'))
    assert [c.id for c in bad] == ["a.x", "a.verify-output", "a.verify-output"] and not any(c.ok for c in bad[1:])
    crashed = checklist.parse_verify("a", _cp(good, rc=3, stderr="boom"))
    assert crashed[-1] == checklist.Check("a.verify-script", False, "exit 3: boom")
    assert checklist.parse_verify("a", _cp("", rc=0)) == [checklist.Check("a.verify-script", False, "exit 0: no checks printed")]


MD_FULL = """# arm
## Pins
- `not.a.check` — a pin bullet, not a machine id
## Machine-verified
- `common.claude-version` — cc
- `setup.origin-push` — push
## Owner-verified
- [ ] OV1: fine.
"""


def test_machine_ids_come_from_the_machine_verified_section_only():
    assert checklist.machine_ids(MD_FULL) == {"common.claude-version", "setup.origin-push"}


def test_a_listed_check_that_was_not_produced_fails():                           # never green by omission
    got = checklist.missing_checks(MD_FULL, [checklist.Check("common.claude-version", True, "")])
    assert got == [checklist.Check("setup.origin-push", False, "listed in the checklist but not produced")]
    assert checklist.missing_checks(MD_FULL, [checklist.Check("common.claude-version", True, ""),
                                              checklist.Check("setup.origin-push", True, "")]) == []


def test_pass2_manifest_difference_shows_the_files_and_asks_the_owner(tmp_state):   # review G6, OD20
    d = Paths("pass1", "dryrun").setup_results; d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"a": "1", "b": "2"}))

    class O:
        def __init__(self, yes): self.yes, self.asked = yes, []
        def confirm(self, text): self.asked.append(text); return self.yes
    assert checklist.manifest_check("pass2", "dryrun", {"a": "1", "b": "2"}, O(True)).ok
    no = O(False)
    c = checklist.manifest_check("pass2", "dryrun", {"a": "1", "b": "3"}, no)
    assert not c.ok and "b (changed)" in c.detail and "b (changed)" in no.asked[0]
    yes = O(True)
    c = checklist.manifest_check("pass2", "dryrun", {"a": "1", "b": "3"}, yes)
    assert c.ok and "owner accepted" in c.detail and "b (changed)" in c.detail
    assert not checklist.manifest_check("pass2", "dryrun", {"a": "1"}, None).ok        # no owner: never accepted
    c = checklist.manifest_check("pass1", "dryrun", {"a": "1"}, None)
    assert c.ok and "recorded (1 files)" in c.detail


def test_pass2_without_a_pass1_manifest_fails_rather_than_crashing(tmp_state):
    c = checklist.manifest_check("pass2", "control", {"a": "1"}, None)
    assert c.id == "setup.manifest-matches-pass1" and not c.ok and "pass 1" in c.detail


def test_owner_answers_cover_every_item_and_a_missing_answer_is_not_ok():
    class O:
        def items(self, items): return {"OV1": (True, "fine", 2.0)}
    rec, secs = checklist.ask_owner(O(), [("OV1", "a"), ("OV2", "b")])
    assert rec == {"OV1": {"ok": True, "note": "fine"}, "OV2": {"ok": False, "note": "no answer recorded"}}
    assert secs == 2.0


def test_cli_setup_prints_each_check_and_exits_nonzero_unless_green(monkeypatch, capsys):
    from runner import cli
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: ("cred", "owner"))
    res = checklist.SetupResult([checklist.Check("a", True, "fine"), checklist.Check("b", False, "bad")], {}, False, 0.0)
    got = []
    monkeypatch.setattr(checklist, "run_setup", lambda *a: got.append(a) or res)
    assert cli.main(["setup", "dry9", "dryrun"]) == 1
    out = capsys.readouterr().out
    assert got == [("dry9", "dryrun", "cred", "owner")] and "FAIL b" in out and "ok   a" in out


def test_cli_shell_runs_an_interactive_container_inside_the_setup_egress_stage(tmp_state, monkeypatch):
    from runner import cli
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    events = []

    class Stage:
        net = "bk-net-x"
        def __init__(self, pass_, arm, phase, hosts, log): events.append(("stage", phase, str(log)))
        def __enter__(self): return self
        def __exit__(self, *e): events.append(("exit",))
    monkeypatch.setattr(checklist.egress, "Stage", Stage)
    monkeypatch.setattr(checklist.subprocess, "call", lambda argv: events.append(("call", argv)) or 0)
    assert cli.main(["shell", "dry9", "dryrun"]) == 0
    argv = events[1][1]
    assert events[0][1] == "setup" and events[-1] == ("exit",)       # torn down: never exec'd past the Stage
    assert "-t" in argv and "-i" in argv and "HISTFILE=/home/actor/.bash_history" in argv
    assert "bk-net-x" in argv and "HTTPS_PROXY=http://egress:3128" in argv


def test_cli_checklist_copies_the_shell_history_without_following_links(tmp_state, monkeypatch, tmp_path, capsys):
    from runner import cli
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    monkeypatch.setattr(checklist, "verify", lambda p_, a, mode: [checklist.Check("x", True, "")])
    (p.home / ".bash_history").write_text("ls\n")
    assert cli.main(["checklist", "dry9", "dryrun"]) == 0
    assert (p.setup_results / "shell-history.txt").read_text() == "ls\n"
    (p.home / ".bash_history").unlink()
    secret = tmp_path / "outside.txt"; secret.write_text("host secret")
    os.symlink(secret, p.home / ".bash_history")
    cli.main(["checklist", "dry9", "dryrun"])
    assert "host secret" not in (p.setup_results / "shell-history.txt").read_text()
