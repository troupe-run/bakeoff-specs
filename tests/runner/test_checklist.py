# tests/runner/test_checklist.py
import dataclasses, gzip, json, os, stat, subprocess
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

# --- preflight rulings and hardening beyond the plan text ------------------------------------------------
FAKE_PAT = "github_pat_FAKE_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"   # fake only, never a real token


def test_every_arm_including_dry_ones_has_the_origin_push_host_check():         # preflight B4
    assert "dryrun" in checklist.HOST_CHECKS
    for arm, ids in checklist.HOST_CHECKS.items():
        assert {"setup.origin-push", "common.no-foreign-model-ids"} <= ids, arm          # always, never computed away


def test_host_check_ids_follow_the_plan_for_real_arms():
    h = checklist.HOST_CHECKS
    assert "github.issues-access" in h["control"] and "github.issues-access" not in h["speckitty"]
    assert "github.issues-access" not in h["dryrun"]
    assert "superpowers.smoke" in h["superpowers"]
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
    monkeypatch.setattr(checklist, "_agent_turns", lambda *a: calls.append("agent") or (0.0, {}, []))

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


def test_shell_history_is_copied_without_following_links(tmp_state, tmp_path):
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    (p.home / ".bash_history").write_text("ls\n")
    assert checklist.copy_shell_history(p)
    assert (p.setup_results / "shell-history.txt").read_text() == "ls\n"
    (p.home / ".bash_history").unlink()
    secret = tmp_path / "outside.txt"; secret.write_text("host secret")
    os.symlink(secret, p.home / ".bash_history")
    assert not checklist.copy_shell_history(p)
    assert "host secret" not in (p.setup_results / "shell-history.txt").read_text()


# --- fix round 1 (controller rulings) --------------------------------------------------------------------
def test_a_check_has_three_statuses_and_n_a_is_never_a_pass_for_a_real_arm():            # FR1 item 1
    na = checklist.Check("github.issues-access", False, "no repo", "n/a")
    assert na.status == "n/a" and not na.ok
    assert checklist.Check("a", True, "").status == "ok" and checklist.Check("a", False, "").status == "fail"
    ok = checklist.Check("a", True, "")
    assert not checklist.green([ok, na], {}) and not checklist.green([ok, na], {}, dry=False)
    assert checklist.green([ok, na], {}, dry=True)
    assert not checklist.green([ok, checklist.Check("b", False, "")], {}, dry=True)


def _records(p, checks):
    d = p.setup_results; d.mkdir(parents=True, exist_ok=True)
    (d / "checklist.json").write_text(json.dumps([dataclasses.asdict(c) for c in checks]))
    (d / "owner-checklist.json").write_text(json.dumps({"OV1": {"ok": True, "note": ""}}))


def test_is_green_counts_n_a_only_for_dry_arms(tmp_state):
    na = checklist.Check("github.issues-access", False, "no repo", "n/a")
    real, dry = Paths("dry9", "control"), Paths("dry9", "dryrun")
    _records(real, [checklist.Check("a", True, ""), na]); _records(dry, [checklist.Check("a", True, ""), na])
    assert not checklist.is_green(real) and checklist.is_green(dry)


def test_old_records_without_a_status_still_load(tmp_state):
    p = Paths("pass1", "control"); d = p.setup_results; d.mkdir(parents=True)
    (d / "checklist.json").write_text(json.dumps([{"id": "a", "ok": True, "detail": ""}]))
    (d / "owner-checklist.json").write_text(json.dumps({}))
    assert checklist.is_green(p)


def test_issues_access_is_n_a_without_a_repo_and_fails_without_a_stage(tmp_state):
    arm = config.load_arm("control")
    na = checklist.issues_access_check(Paths("dry9", "control"), arm, "dry9", object())
    assert na.status == "n/a" and "dry9" in na.detail
    no_stage = checklist.issues_access_check(Paths("pass1", "control"), arm, "pass1", None)
    assert no_stage.status == "fail" and not no_stage.ok


def _turns(*rows):
    return [{"prompt": i, "turn": n, "outcome": o} for n, (i, o) in enumerate(rows, 1)]


def test_agent_turns_check_needs_the_last_turn_of_every_prompt_ok():                        # FR1 item 2
    arm = dataclasses.replace(config.load_arm("dryrun"), setup_agent=["a", "b"])
    assert checklist.agent_turns_check(arm, _turns((0, "ok"), (1, "ok"))).ok
    assert checklist.agent_turns_check(arm, _turns((0, "timeout"), (0, "ok"), (1, "ok"))).ok   # owner reply fixed it
    c = checklist.agent_turns_check(arm, _turns((0, "ok"), (1, "ok"), (1, "is_error")))
    assert not c.ok and "is_error" in c.detail
    for bad in ("timeout", "no_result"):
        assert not checklist.agent_turns_check(arm, _turns((0, "ok"), (1, bad))).ok
    missing = checklist.agent_turns_check(arm, _turns((0, "ok")))
    assert not missing.ok and "never ran" in missing.detail
    assert checklist.agent_turns_check(dataclasses.replace(arm, setup_agent=[]), []) is None   # T10 FR1: omitted


def test_the_agent_turns_check_exists_exactly_for_arms_with_setup_prompts():      # T10 FR1 item 1
    for arm in checklist.HOST_CHECKS:
        assert ("setup.agent-turns" in checklist.HOST_CHECKS[arm]) == bool(config.load_arm(arm).setup_agent), arm


def test_a_shell_session_marks_setup_dirty_before_it_starts(tmp_state, monkeypatch):       # FR1 item 3
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)

    class Stage:
        net = "n"
        def __init__(self, *a): pass
        def __enter__(self): return self
        def __exit__(self, *e): pass
    monkeypatch.setattr(checklist.egress, "Stage", Stage)
    seen = []
    monkeypatch.setattr(checklist.subprocess, "call", lambda argv: seen.append(checklist.is_dirty(p)) or 0)
    _records(p, [checklist.Check("a", True, "")])
    assert checklist.is_green(p)
    checklist.interactive_shell("dry9", "dryrun")
    assert seen == [True] and checklist.is_dirty(p) and not checklist.is_green(p)
    assert "since" in json.loads(checklist.dirty_marker(p).read_text())
    with pytest.raises(checklist.NotReady, match="dirty"):
        checklist.require_clean_green(p)


def test_require_clean_green_refuses_a_setup_that_is_not_green(tmp_state):
    p = Paths("dry9", "dryrun")
    with pytest.raises(checklist.NotReady, match="not green"):
        checklist.require_clean_green(p)
    _records(p, [checklist.Check("a", True, "")])
    checklist.require_clean_green(p)


def test_interactive_shell_refuses_a_parked_arm(tmp_state):                              # FR1 item 10
    with pytest.raises(checklist.NotReady, match="bmad"):
        checklist.interactive_shell("dry9", "bmad")


def test_cli_checklist_runs_the_full_recheck_and_its_exit_code_is_the_result(monkeypatch):
    from runner import cli
    monkeypatch.setattr(cli, "_owner_for", lambda arm: "owner")
    got = []
    res = checklist.SetupResult([checklist.Check("a", True, "")], {}, False, 0.0)
    monkeypatch.setattr(checklist, "recheck", lambda *a: got.append(a) or res)
    assert cli.main(["checklist", "dry9", "dryrun"]) == 1
    monkeypatch.setattr(checklist, "recheck", lambda *a: dataclasses.replace(res, green=True))
    assert cli.main(["checklist", "dry9", "dryrun"]) == 0
    assert got == [("dry9", "dryrun", "owner")]


def test_the_applied_model_env_is_what_sessions_get():                                  # FR1 item 4
    pins = config.load_pins()
    env = checklist.applied_model_env(pins, config.load_arm("control"), "pass1")
    for k in ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
              "CLAUDE_CODE_SUBAGENT_MODEL", "BK_MODEL"):
        assert env[k] == pins.model
    full = credentials.session_env(pins, config.load_arm("control"), role="arm", isolated=False, pass_="pass1")
    assert env == {k: v for k, v in full.items() if "MODEL" in k}


def test_a_missing_manifest_path_fails_the_manifest_check_naming_it():                    # FR1 item 7
    c = checklist.manifest_check("pass1", "dryrun", {"a": "1"}, missing=["openspec"])
    assert not c.ok and "openspec" in c.detail
    assert checklist.manifest_check("pass1", "dryrun", {"a": "1"}, missing=[]).ok


def test_arms_whose_setup_creates_nothing_in_the_repo_list_no_manifest_paths():
    for arm in ("control", "superpowers", "dryrun"):
        assert config.load_arm(arm).manifest_paths == [], arm


def test_a_broken_arm_toml_does_not_break_importing_checklist(tmp_path):                  # FR1 item 8
    import shutil, sys
    arms = tmp_path / "arms"; shutil.copytree(config.ARMS_DIR, arms)
    (arms / "broken.toml").write_text("this is [not toml")
    code = ("import sys; from pathlib import Path; from runner import config; config.ARMS_DIR = Path(sys.argv[1]); "
            "import runner.checklist as c; print(sorted(c.HOST_CHECKS)[:1], 'control' in c.HOST_CHECKS, "
            "'setup.origin-push' in c.HOST_CHECKS['control'])")
    r = subprocess.run([sys.executable, "-c", code, str(arms)], capture_output=True, text=True,
                       cwd=checklist.REPO_ROOT)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "['bmad'] True True"


# --- Task 10: the checklists and verify scripts for control, superpowers, openspec, bmad -------------------
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "checklists"
DONE_ARMS = config.all_arms()                                    # Task 11: all seven real arms
SECTIONS = ["## Source", "## Pins", "## Setup (what the runner runs)", "## Machine-verified", "## Owner-verified",
            "## Known traps"]


def md_ids(arm):
    """The `## Machine-verified` ids of an arm's checklist (only that section: other sections may quote ids)."""
    return checklist.machine_ids((ROOT / f"{arm}.md").read_text())


def script_ids(arm):
    """Every id a `check <id> …` CALL names in the arm's script and lib.sh (line-start calls only, so prose in a
    comment such as 'fails its check rather than…' is never read as an id)."""
    text = (ROOT / "verify" / f"{arm}.sh").read_text() + (ROOT / "verify" / "lib.sh").read_text()
    return set(re.findall(r"^\s*check ([a-z0-9.-]+) ", text, re.M))


@pytest.mark.parametrize("arm", DONE_ARMS)
def test_every_machine_id_in_the_md_is_named_by_a_check_call_or_host_checks_and_vice_versa(arm):   # m14: added
    """Static bullets are the script's ids plus the host ids that are never computed away; every id that can be
    computed away is documented as a `- (computed)` bullet instead (T10 FR1 item 1)."""
    text = (ROOT / f"{arm}.md").read_text()
    a = config.load_arm(arm)
    conditional = checklist.conditional_ids(a)
    assert md_ids(arm) == script_ids(arm) | (checklist.HOST_CHECKS[arm] - conditional)
    assert checklist.computed_ids(text) == conditional
    assert checklist.HOST_CHECKS[arm] - md_ids(arm) <= checklist.computed_ids(text)


@pytest.mark.parametrize("arm", DONE_ARMS)
def test_every_checklist_has_the_six_sections_in_order_with_owner_items(arm):
    text = (ROOT / f"{arm}.md").read_text()
    at = [text.find(s + "\n") for s in SECTIONS]
    assert -1 not in at and at == sorted(at), dict(zip(SECTIONS, at))
    assert checklist.owner_items(text)


@pytest.mark.parametrize("arm", DONE_ARMS)
def test_every_checklist_lists_the_origin_checks(arm):                                        # preflight B4
    assert {"common.origin", "setup.origin-push"} <= md_ids(arm)


def _section(text, name):
    m = re.search(rf"^{re.escape(name)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


@pytest.mark.parametrize("arm", DONE_ARMS)
def test_every_setup_step_cites_its_source_section(arm):
    steps = [l for l in _section((ROOT / f"{arm}.md").read_text(), "## Setup (what the runner runs)").splitlines()
             if re.match(r"^\d+\. |^Nothing", l)]
    assert steps and all("§" in l for l in steps), [l for l in steps if "§" not in l]


@pytest.mark.parametrize("arm", ["superpowers", "openspec", "bmad", "speckit", "speckitty", "ccsdd"])
def test_method_checklists_cite_their_candidates_section(arm):
    src = _section((ROOT / f"{arm}.md").read_text(), "## Source")
    cite = config.load_arm(arm).citation                                   # e.g. "CANDIDATES §1.1"
    assert cite.replace("CANDIDATES", "research/CANDIDATES.md") in src


def test_superpowers_setup_is_the_documented_smoke_test_and_nothing_in_the_repo():   # CANDIDATES §1.1 items 2-3
    a = config.load_arm("superpowers")
    assert (a.setup_shell, a.setup_agent, a.setup_post_shell) == ([], [], [])
    assert a.smoke == config.Smoke("Let's make a react todo list", "brainstorming")
    assert a.manifest_paths == []            # no init: setup creates nothing in the repo (controller ruling)
    assert [p.name for p in a.plugins] == ["superpowers"] and a.plugins[0].sha


def test_openspec_setup_is_init_telemetry_off_and_the_principles_as_context():        # CANDIDATES §1.3
    a = config.load_arm("openspec")
    assert a.setup_shell[:2] == ["openspec init --tools claude", "openspec config set telemetry.enabled false"]
    assert "/setup/project-principles.md" in a.setup_shell[2] and "context: |" in a.setup_shell[2]
    assert (a.setup_agent, a.setup_post_shell, a.plugins) == ([], [], [])
    assert a.manifest_paths == [".claude", "openspec", "~/.config/openspec"]


def test_bmad_setup_is_bmad_setup_gh_ticketing_principles_then_script_locks():         # CANDIDATES §1.5
    a = config.load_arm("bmad")
    assert a.setup_shell == [] and len(a.setup_agent) == 3
    assert "`bmad setup`" in a.setup_agent[0] and "gh store" in a.setup_agent[1]
    assert a.setup_agent[2].endswith("{principles}")
    assert "uv lock --script" in a.setup_post_shell[0] and "_bmad/*/scripts/*.py" in a.setup_post_shell[0]
    assert a.manifest_paths == ["_bmad"]
    assert [p.name for p in a.plugins] == ["bmad-method", "bmad-core-tools"]


def test_verify_containers_see_the_principles_read_only(tmp_state, monkeypatch):   # openspec.context compares them
    seen = []
    monkeypatch.setattr(checklist.repo, "recover", lambda p: None)
    monkeypatch.setattr(checklist.docker, "run", lambda s, timeout: seen.append(s) or _cp('{"id":"a","ok":true,"detail":""}\n'))
    checklist.verify(Paths("dry9", "openspec"), config.load_arm("openspec"), "setup")
    m = {x.ctr: x for x in seen[0].mounts}
    assert m["/setup/project-principles.md"].host == checklist.PRINCIPLES and m["/setup/project-principles.md"].ro
    assert m["/checks"].ro and seen[0].network == "none"


# --- Task 10 fix round 1: vacuous host checks are omitted, not recorded ok --------------------------------
def _arm(name, **kw):
    return dataclasses.replace(config.load_arm(name), **kw)


def _route(monkeypatch, route):
    real = config.load_pins
    monkeypatch.setattr(config, "load_pins", lambda: dataclasses.replace(real(), plugin_route=route))


def test_agent_turns_is_omitted_without_prompts_and_present_with_them():
    assert "setup.agent-turns" not in checklist.host_check_ids(_arm("control"))
    assert "setup.agent-turns" in checklist.host_check_ids(_arm("bmad"))
    assert "setup.agent-turns" in checklist.host_check_ids(_arm("control", setup_agent=["x"]))


def test_manifest_check_follows_the_effective_manifest_list(monkeypatch):            # route-dependent
    _route(monkeypatch, "plugin-dir")
    assert checklist.effective_manifest_paths(_arm("superpowers")) == []
    assert "setup.manifest-created" not in checklist.host_check_ids(_arm("superpowers"))
    assert "setup.manifest-created" not in checklist.host_check_ids(_arm("control"))
    assert "setup.manifest-created" in checklist.host_check_ids(_arm("openspec"))
    _route(monkeypatch, "marketplace")
    assert checklist.effective_manifest_paths(_arm("superpowers")) == ["~/.claude/plugins/cache"]
    assert "setup.manifest-created" in checklist.host_check_ids(_arm("superpowers"))
    assert "setup.manifest-created" not in checklist.host_check_ids(_arm("control"))   # no plugins


def test_entry_commands_is_omitted_when_no_slash_command_is_needed():
    # A command arm whose [drive] genuinely needs no slash command (plain entries, empty must_run): check omitted.
    bare = _arm("openspec", entry="{handoff}", bug_entry="{handoff}", must_run=[], must_run_source="s")
    assert checklist.needed_commands(bare) == []
    assert "openspec.entry-commands" not in checklist.host_check_ids(bare)
    assert checklist.needed_commands(_arm("control")) == []                    # the real arm with nothing needed
    a = _arm("openspec", entry="{handoff}", bug_entry="{handoff}", must_run=["/opsx:archive"], must_run_source="s")
    assert checklist.needed_commands(a) == ["opsx:archive"]
    assert "openspec.entry-commands" in checklist.host_check_ids(a)
    assert "control.entry-commands" not in checklist.host_check_ids(_arm("control", must_run=["/x"],
                                                                         must_run_source="s"))  # not a command arm


def test_the_conditional_ids_are_the_three_computable_host_checks():
    assert checklist.conditional_ids(_arm("openspec")) == {"setup.agent-turns", "setup.manifest-created",
                                                           "openspec.entry-commands"}
    assert checklist.conditional_ids(_arm("control")) == {"setup.agent-turns", "setup.manifest-created"}


MD_COMPUTED = MD_FULL.replace("## Owner-verified", "- (computed) `setup.agent-turns` — when prompts exist\n## Owner-verified")


def test_computed_bullets_are_not_static_ids_and_missing_checks_uses_the_computed_set():
    assert checklist.computed_ids(MD_COMPUTED) == {"setup.agent-turns"}
    assert "setup.agent-turns" not in checklist.machine_ids(MD_COMPUTED)
    done = [checklist.Check("common.claude-version", True, ""), checklist.Check("setup.origin-push", True, "")]
    assert checklist.missing_checks(MD_COMPUTED, done) == []                  # computed away: nothing missing
    got = checklist.missing_checks(MD_COMPUTED, done, expected={"setup.agent-turns"})
    assert got == [checklist.Check("setup.agent-turns", False, "listed in the checklist but not produced")]


def _host_checks(tmp_state, monkeypatch, arm, names=frozenset(), missing=()):
    import shutil
    p = Paths("dry9", arm.name); shutil.rmtree(p.setup_results, ignore_errors=True); p.setup_results.mkdir(parents=True)
    monkeypatch.setattr(checklist.repo, "recover", lambda p: None)
    monkeypatch.setattr(checklist.commands, "listing", lambda p, a: checklist.commands.Listing(set(names), []))
    calls = []
    monkeypatch.setattr(checklist, "manifest_full", lambda p, a: calls.append(a) or ({"f": "1"}, list(missing)))
    monkeypatch.setattr(checklist, "_origin_push", lambda p: checklist.Check("setup.origin-push", True, ""))
    monkeypatch.setattr(checklist, "issues_access_check",
                        lambda *a: checklist.Check("github.issues-access", True, ""))
    return {c.id: c for c in checklist.host_checks(p, arm, "dry9", None, None)}, calls


def test_host_checks_omit_the_empty_checks_and_produce_exactly_host_check_ids(tmp_state, monkeypatch):
    _route(monkeypatch, "plugin-dir")
    for arm in (_arm("control"), _arm("superpowers"), _arm("openspec")):
        got, calls = _host_checks(tmp_state, monkeypatch, arm)
        smoke = {f"{arm.name}.smoke"} if arm.smoke else set()          # _smoke is run by run_setup, not here
        agent = {"setup.agent-turns"} if arm.setup_agent else set()     # agent_turns_check, run by run_setup
        assert set(got) == checklist.host_check_ids(arm) - smoke - agent, arm.name
        assert bool(calls) == bool(checklist.effective_manifest_paths(arm)), arm.name   # no container when empty


def test_present_entry_commands_is_falsifiable(tmp_state, monkeypatch):
    a = _arm("superpowers")                                     # real [drive]: must_run is one plugin command
    [cmd] = checklist.needed_commands(a)
    got, _ = _host_checks(tmp_state, monkeypatch, a, names={"superpowers:brainstorming"})
    assert not got["superpowers.entry-commands"].ok and cmd in got["superpowers.entry-commands"].detail
    got, _ = _host_checks(tmp_state, monkeypatch, a, names={cmd})
    assert got["superpowers.entry-commands"].ok


def test_needed_commands_lists_each_command_once_in_first_seen_order():
    assert checklist.needed_commands(_arm("openspec")) == ["opsx:propose", "opsx:archive"]   # entry == bug_entry
    assert checklist.needed_commands(_arm("speckit")) == [
        "speckit-specify", "speckit-bug-assess", "speckit-converge", "speckit-tasks", "speckit-taskstoissues"]


def test_present_manifest_check_on_route_a_is_falsifiable(tmp_state, monkeypatch):
    _route(monkeypatch, "marketplace")
    got, calls = _host_checks(tmp_state, monkeypatch, _arm("superpowers"), missing=["~/.claude/plugins/cache"])
    assert calls and not got["setup.manifest-created"].ok


# --- Task 20 fix round 1 (MEDIUM: owner-shell interventions can be forged) --------------------------------
def test_record_owner_shell_commit_appends_to_a_harness_side_file_under_setup_results(tmp_state):
    """The arm has no write access to `p.setup_results` (outside its repo and home) — this file, not a
    pattern-matched git-log subject, is what `evidence.finalise` trusts for owner-shell interventions."""
    p = Paths("dry9", "dryrun")
    p.setup_results.mkdir(parents=True)
    checklist.record_owner_shell_commit(p.setup_results, "aaa111")
    checklist.record_owner_shell_commit(p.setup_results, "bbb222")
    recorded = json.loads((p.setup_results / checklist.OWNER_SHELL_COMMITS_FILE).read_text())
    assert [r["sha"] for r in recorded] == ["aaa111", "bbb222"]
    assert all("at" in r for r in recorded)


def test_recheck_records_the_sha_it_commits_from_a_dirty_repo(tmp_state, monkeypatch):
    """`checklist.recheck` (the `runner checklist` CLI, run after an owner `runner shell` session) must record
    every commit sha it makes — not just leave the arm's forgeable git-log subject as the only trace."""
    calls = []

    class Stage:
        net = "bk-net-x"
        def __init__(self, *a): pass
        def __enter__(self): return self
        def __exit__(self, *e): pass
    p = Paths("dry9", "dryrun")
    p.setup_results.mkdir(parents=True)
    monkeypatch.setattr(checklist.gitops, "state", lambda p_: type("S", (), {"dirty": True})())
    monkeypatch.setattr(checklist.gitops, "commit_all", lambda p_, who, msg: "sha-from-recheck")
    monkeypatch.setattr(checklist, "record_owner_shell_commit", lambda out, sha: calls.append((out, sha)))
    monkeypatch.setattr(checklist.egress, "Stage", Stage)
    monkeypatch.setattr(checklist, "verify", lambda *a: [])
    monkeypatch.setattr(checklist, "host_checks", lambda *a, **k: [])
    monkeypatch.setattr(checklist, "_read_md", lambda n: MD)
    monkeypatch.setattr(checklist, "missing_checks", lambda *a: [])
    monkeypatch.setattr(checklist, "copy_shell_history", lambda p_: True)
    monkeypatch.setattr(checklist.repo, "recover", lambda p_: None)
    monkeypatch.setattr(checklist.repo, "snapshot", lambda p_, n: None)
    checklist.recheck("dry9", "dryrun", None)
    assert calls == [(p.setup_results, "sha-from-recheck")]


# --- Task 11: speckit, speckitty (+ beads), ccsdd ----------------------------------------------------------------
def test_done_arms_are_all_seven_real_arms():
    assert sorted(DONE_ARMS) == ["bmad", "ccsdd", "control", "openspec", "speckit", "speckitty", "superpowers"]


def test_speckit_setup_is_the_existing_repo_init_the_bug_extension_and_the_constitution():   # CANDIDATES §1.2
    a = config.load_arm("speckit")
    assert a.setup_shell == ["specify init --here --force --integration claude", "specify extension add bug"]
    assert a.setup_agent == ["/speckit-constitution {principles}"]
    assert (a.setup_post_shell, a.plugins) == ([], [])
    assert a.manifest_paths == [".claude", ".specify"]
    assert a.export_after == "/speckit-tasks"                                  # Task 12's OD24 = B, unchanged


def test_speckitty_setup_is_init_verify_beads_then_the_tracker_binding_with_its_egress_decision():  # §1.4, §2.1
    a = config.load_arm("speckitty")
    s = a.setup_shell
    assert s[:2] == ["spec-kitty init . --ai claude", "spec-kitty verify-setup"]
    assert s.index("bd metrics off") < s.index("bd init") < s.index("bd setup claude")          # telemetry off first
    bind = next(c for c in s if "tracker bind" in c)
    assert bind == "SPEC_KITTY_ENABLE_SAAS_SYNC=1 spec-kitty tracker bind --provider beads --workspace beads"
    assert s.index(bind) > s.index("bd init")
    egress = s[-1]                                                             # recorded after the binding exists
    assert "EGRESS_PERMITTED" in egress and "save_tracker_config" in egress and 'c.provider == "beads"' in egress
    assert a.setup_agent == ["/spec-kitty.charter {principles}"]
    assert (a.setup_post_shell, a.plugins) == ([], [])
    assert {"~/.claude/commands", "~/.claude/skills", "~/.config/bd", ".beads/config.yaml"} <= set(a.manifest_paths)


def test_ccsdd_setup_is_the_skills_installer_then_steering():                  # CANDIDATES §1.7a
    a = config.load_arm("ccsdd")
    assert a.setup_shell == ["cc-sdd --claude-skills"]
    assert a.setup_agent == ["/kiro-steering\n\n{principles}"]
    assert (a.setup_post_shell, a.plugins) == ([], [])
    assert a.manifest_paths == [".claude", ".kiro/settings", "CLAUDE.md"]


@pytest.mark.parametrize("arm", ["speckit", "speckitty", "ccsdd"])
def test_the_three_arms_get_every_computed_host_check(arm):
    """Each has setup prompts, a manifest list and slash commands to require: nothing is computed away."""
    assert checklist.conditional_ids(config.load_arm(arm)) <= checklist.HOST_CHECKS[arm]
    assert ("github.issues-access" in checklist.HOST_CHECKS[arm]) == (arm != "speckitty")    # beads: no GitHub


def test_speckitty_entry_commands_need_the_charter_driven_workflow():
    assert checklist.needed_commands(config.load_arm("speckitty")) == ["spec-kitty.specify", "spec-kitty.accept",
                                                                       "spec-kitty.merge"]
    assert "speckit-taskstoissues" in checklist.needed_commands(config.load_arm("speckit"))     # OD24 B export


# --- Task 11 fix round 1 ---------------------------------------------------------------------------------------
def test_speckitty_sessions_have_the_saas_sync_flag_off_and_no_upgrade_check():        # FR1 items 2, 3
    """Provisional ruling: spec-kitty's SaaS flag is OFF in arm sessions — one explicit config value (spec-kitty reads
    only 1/true/yes/y/on as on), so turning it on is a config change."""
    a = config.load_arm("speckitty")
    env = credentials.session_env(config.load_pins(), a, role="arm", isolated=False, pass_="pass1")
    assert env["SPEC_KITTY_ENABLE_SAAS_SYNC"] == "0"
    assert env["SPEC_KITTY_NO_UPGRADE_CHECK"] == "1"
    raw = (config.ARMS_DIR / "speckitty.toml").read_text()
    assert "SPEC_KITTY_ENABLE_SAAS_SYNC" in raw.split("[egress]")[0]          # the switch lives in the arm's env


def test_speckit_md_says_the_adoption_branch_is_skipped_on_purpose():                    # FR1 item 4
    assert "adoption branch" in _section((ROOT / "speckit.md").read_text(), "## Setup (what the runner runs)")


def test_speckitty_md_records_the_inert_binding_and_beads_via_bd_prime():                # FR1 item 2
    text = (ROOT / "speckitty.md").read_text()
    assert "inert" in text and "bd prime" in text and "speckitty.hosted-egress-refused" in md_ids("speckitty")


def test_speckitty_manifest_lists_the_setup_files_both_inits_create():                   # FR1 item 5
    m = set(config.load_arm("speckitty").manifest_paths)
    assert {"AGENTS.md", ".agents", ".beads/hooks", ".gitignore", ".claudeignore", ".gitattributes"} <= m


# volatile paths (FR1 item 6): excluded from the pass-2 comparison, each with a kind and a reason
def _arm_with(tmp_path, monkeypatch, setup_extra: str):
    import shutil
    arms = tmp_path / "arms"; shutil.copytree(config.ARMS_DIR, arms)
    t = (arms / "dryrun.toml").read_text()
    t = t.replace("[setup]\n", "[setup]\n" + setup_extra + "\n", 1)
    if "manifest_paths" in setup_extra:
        t = re.sub(r"^manifest_paths = \[\].*\n", "", t, count=1, flags=re.M)
    (arms / "dryrun.toml").write_text(t)
    monkeypatch.setattr(config, "ARMS_DIR", arms)
    return lambda: config.load_arm("dryrun")


@pytest.mark.parametrize("extra,msg", [
    ('manifest_paths = [".x"]\nvolatile_paths = [{ path = ".x/a", kind = "install-stamp" }]', "why"),
    ('manifest_paths = [".x"]\nvolatile_paths = [{ path = ".x/a", kind = "other", why = "w" }]', "kind"),
    ('manifest_paths = [".x"]\nvolatile_paths = [{ path = ".y/a", kind = "install-stamp", why = "w" }]', "manifest"),
])
def test_a_volatile_path_needs_a_kind_a_reason_and_a_manifest_path_to_live_in(tmp_path, monkeypatch, extra, msg):
    load = _arm_with(tmp_path, monkeypatch, extra)
    with pytest.raises(config.ConfigError, match=msg):
        load()


def test_volatile_paths_default_to_none():
    assert config.load_arm("openspec").volatile_paths == []


@pytest.mark.parametrize("arm", ["speckit", "speckitty"])
def test_model_written_volatile_paths_are_what_the_checklist_owner_checks(arm):
    """A model-written entry must be the agent turn's output that the checklist names (the owner reads it)."""
    text = (ROOT / f"{arm}.md").read_text()
    mw = [v.path for v in config.load_arm(arm).volatile_paths if v.kind == "model-written"]
    assert mw and all(f"`{p}" in text for p in mw), mw
