# tests/runner/test_verify_docker.py — the verify scripts, run for real in the arm images (review Q-11, Q-13).
# 1. Each script prints exactly the non-host ids its checklist md lists.
# 2. Falsifiability (controller ruling): for every check a script prints, breaking the thing it checks makes THAT
#    check fail — and only that one, so the failure is the check's own and not a side effect.
# bmad is PARKED (preflight B2, arms/bmad.toml): its real-image tests skip naming the park. Its script logic is
# still exercised against fixtures on the base image, which does not depend on the parked image.
import dataclasses, json, os, shutil
from pathlib import Path
import pytest
from runner import checklist, config, docker, gitops, images, repo
from runner.docker import Mount
from runner.paths import Paths
from tests.runner.test_checklist import DONE_ARMS, md_ids

pytestmark = pytest.mark.docker

PASS = "dry9"
PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def parked(arm: str) -> str | None:
    e = images.lock().get("arms", {}).get(arm) or {}
    if not e.get("id") or e.get("error"):
        return (f"{arm} is PARKED (preflight B2; see arms/{arm}.toml): no built image in the lock "
                f"({e.get('error', 'missing')})")
    return None


def skip_if_parked(arm: str) -> None:
    if (why := parked(arm)):
        pytest.skip(why)


@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    for arm in DONE_ARMS:
        assert not docker.running(f"bakeoff.run={PASS}/{arm}"), arm
        assert not docker.sweep(f"bakeoff.run={PASS}/{arm}")["networks"], arm


def run(p: Paths, arm: config.Arm, mode: str = "setup", *, image: str | None = None, extra=(), env=None) -> dict:
    """checklist.verify's own container spec, optionally with a different image, extra mounts or env."""
    s = checklist.verify_spec(p, arm, mode)
    s = dataclasses.replace(s, image=image or s.image, mounts=[*s.mounts, *extra], env={**s.env, **(env or {})})
    return {c.id: c for c in checklist.parse_verify(arm.name, docker.run(s, timeout=300))}


def failing(got: dict) -> set[str]:
    return {i for i, c in got.items() if not c.ok}


def script_only_ids(arm: str) -> set[str]:
    return md_ids(arm) - checklist.HOST_CHECKS[arm]


def fresh(monkeypatch, p: Paths, backup: Path, n) -> None:
    """Point the state root at a NEW directory holding a copy of `backup` (p's base after setup). Docker Desktop's
    file sharing serves stale content for a bind-mounted tree that is deleted and rebuilt at the same path, so a
    case never restores in place: every case gets a never-mounted copy."""
    from runner import paths
    monkeypatch.setattr(paths, "STATE", backup.parent / f"state-{n}")
    shutil.copytree(backup, p.base, symlinks=True)


def common_breaks(p: Paths) -> dict:
    """name -> (mutate or None, failing set, env): one break for each lib.sh `common` check but no-foreign-plugins
    (each arm breaks that its own way). Runs on the arm's own image."""
    return {
        "a foreign git identity": (lambda: gitops.git(p, "config", "user.name", "Someone", write=True),
                                   {"common.git-identity"}, {}),
        "origin elsewhere": (lambda: gitops.git(p, "remote", "set-url", "origin", "/tmp/elsewhere.git", write=True),
                             {"common.origin"}, {}),
        "auto-memory on": (None, {"common.isolation-env"}, {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0"}),
        "another Claude Code expected": (None, {"common.claude-version"},
                                         {"BK_EXPECT_CLAUDE_VERSION": "2.1.280 (Claude Code)"}),
    }


def run_breaks(monkeypatch, p, arm, backup, cases, extra=lambda: [], tag="c") -> dict:
    """Each case on its own never-mounted copy of the post-setup state; returns {name: failing set}."""
    seen = {}
    for n, (name, (mutate, _, env)) in enumerate(cases.items()):
        fresh(monkeypatch, p, backup, f"{tag}{n}")
        if mutate:
            mutate()
        seen[name] = failing(run(p, arm, extra=extra(), env=env))
    return seen


def assert_every_script_id_falsified(arm: str, wants) -> None:
    """T10 FR1 item 2: every id the arm's script prints (common ones included) fails in at least one case."""
    assert set().union(*wants) == script_only_ids(arm), script_only_ids(arm) - set().union(*wants)


# ---- 1. the scripts print what the mds list ------------------------------------------------------------------
@pytest.mark.parametrize("arm", DONE_ARMS)
def test_the_script_prints_exactly_the_non_host_ids_of_the_md(arm, tmp_state):
    skip_if_parked(arm)
    p = Paths(PASS, arm); repo.init(p, arm, PASS)
    printed = {c.id for c in checklist.verify(p, config.load_arm(arm), "setup")}
    assert printed == script_only_ids(arm)


@pytest.mark.parametrize("arm", ["superpowers", "bmad"])
def test_vendored_plugins_pass_their_version_checks_offline(arm, tmp_state):     # OD9 B
    skip_if_parked(arm)
    p = Paths(PASS, arm); repo.init(p, arm, PASS)
    got = {c.id: c.ok for c in checklist.verify(p, config.load_arm(arm), "step")}
    assert got[f"{arm}.plugin-version"] and got["common.claude-version"] and got["common.no-foreign-plugins"]


STEP_IDS = {"control": set(), "superpowers": {"superpowers.plugin-version"}, "bmad": {"bmad.plugin-version"},
            "openspec": {"openspec.version"}, "speckit": {"speckit.version"},
            "speckitty": {"speckitty.version", "beads.version"}, "ccsdd": {"ccsdd.version"}}


@pytest.mark.parametrize("arm", DONE_ARMS)
def test_step_mode_prints_only_the_common_checks_and_the_version(arm, tmp_state):
    skip_if_parked(arm)
    p = Paths(PASS, arm); repo.init(p, arm, PASS)
    got = {c.id for c in checklist.verify(p, config.load_arm(arm), "step")}
    common = {"common.claude-version", "common.isolation-env", "common.git-identity", "common.no-foreign-plugins",
              "common.origin"}
    assert got == common | STEP_IDS[arm]


# ---- 2. control ---------------------------------------------------------------------------------------------
def test_control_fresh_repo_passes_every_script_check(tmp_state):
    p = Paths(PASS, "control"); repo.init(p, "control", PASS)
    got = {c.id: c for c in checklist.verify(p, config.load_arm("control"), "setup")}
    assert not failing(got), [got[i] for i in failing(got)]


def _control_mutations(p: Paths):
    def write(rel, text="x"):
        f = p.repo / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)

    def home(rel):
        (p.home / rel).mkdir(parents=True, exist_ok=True)

    def commit():
        write("src.py", "print(1)\n"); gitops.commit_all(p, gitops.IDENTITY, "a file")
    return {
        "CLAUDE.md in the repo": (lambda: write("CLAUDE.md"), {"control.no-method", "control.empty-repo"}),
        "AGENTS.md in the repo": (lambda: write("AGENTS.md"), {"control.no-method", "control.empty-repo"}),
        ".claude/skills in the repo": (lambda: write(".claude/skills/x/SKILL.md"), {"control.no-method", "control.empty-repo"}),
        ".mcp.json in the repo": (lambda: write(".mcp.json", "{}"), {"control.no-method", "control.empty-repo"}),
        "user-scope commands": (lambda: home(".claude/commands"), {"control.no-method"}),
        "user-scope skills": (lambda: home(".claude/skills"), {"control.no-method"}),
        "user-scope agents": (lambda: home(".claude/agents"), {"control.no-method"}),
        "CLAUDE.local.md in the repo": (lambda: write("CLAUDE.local.md"), {"control.no-method", "control.empty-repo"}),
        "user-scope CLAUDE.md": (lambda: (p.config_dir / "CLAUDE.md").write_text("x"), {"control.no-method"}),
        "user-scope output styles": (lambda: home(".claude/output-styles"), {"control.no-method"}),
        "user-scope hooks": (lambda: (p.config_dir / "settings.json").write_text(json.dumps(
            {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}})),
                             {"control.no-method"}),
        "user-scope output style setting": (lambda: (p.config_dir / "settings.json").write_text(
            json.dumps({"outputStyle": "Explanatory"})), {"control.no-method"}),
        "CLAUDE.md above the repo": (lambda: (p.work / "CLAUDE.md").write_text("x"), {"control.no-method"}),
        "CLAUDE.local.md above the repo": (lambda: (p.work / "CLAUDE.local.md").write_text("x"), {"control.no-method"}),
        "a committed file": (commit, {"control.empty-repo"}),
        "an untracked file": (lambda: write("notes.txt"), {"control.empty-repo"}),
        "a foreign git identity": (lambda: gitops.git(p, "config", "user.name", "Someone", write=True),
                                   {"common.git-identity"}),
        "origin elsewhere": (lambda: gitops.git(p, "remote", "set-url", "origin", "/tmp/elsewhere.git", write=True),
                             {"common.origin"}),
        "an installed plugin": (lambda: (p.config_dir / "plugins").mkdir(parents=True, exist_ok=True) or
                                (p.config_dir / "plugins" / "installed_plugins.json").write_text(
                                    json.dumps({"plugins": {"superpowers@claude-plugins-official": []}})),
                                {"common.no-foreign-plugins"}),
    }


def test_every_control_check_fails_when_what_it_checks_is_broken(tmp_state, tmp_path, monkeypatch):
    arm, p = config.load_arm("control"), Paths(PASS, "control"); repo.init(p, "control", PASS)
    backup = tmp_path / "backup"; shutil.copytree(p.base, backup, symlinks=True)
    seen = {}
    for n, (name, (mutate, want)) in enumerate(_control_mutations(p).items()):
        fresh(monkeypatch, p, backup, n)
        mutate()
        seen[name] = failing(run(p, arm))
    fresh(monkeypatch, p, backup, "env")
    seen["auto-memory on"] = failing(run(p, arm, env={"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0"}))
    seen["another Claude Code expected"] = failing(run(p, arm, env={"BK_EXPECT_CLAUDE_VERSION": "2.1.280 (Claude Code)"}))
    want = {n: w for n, (_, w) in _control_mutations(p).items()} | {
        "auto-memory on": {"common.isolation-env"}, "another Claude Code expected": {"common.claude-version"}}
    assert seen == want
    assert_every_script_id_falsified("control", want.values())


def test_harmless_user_settings_do_not_trip_control_no_method(tmp_state):
    """The check reads hooks and outputStyle, not the file's existence: a settings.json without them passes."""
    arm, p = config.load_arm("control"), Paths(PASS, "control"); repo.init(p, "control", PASS)
    (p.config_dir / "settings.json").write_text(json.dumps({"permissions": {"allow": []}}))
    assert not failing(run(p, arm))


# ---- 3. superpowers -----------------------------------------------------------------------------------------
def _export_plugins(p: Paths, arm: config.Arm, dest: Path) -> None:
    """Copy the image's vendored /opt/plugins out to a host dir (in a container; nothing runs on the host)."""
    dest.mkdir(parents=True)
    s = checklist.arm_spec(p, arm, ["bash", "-c", "cp -r /opt/plugins/. /out/"], extra=[Mount(dest, "/out", False)],
                           name="export")
    r = docker.run(s, timeout=120)
    assert r.returncode == 0, r.stderr


def _edit_json(f: Path, fn) -> None:
    d = json.loads(f.read_text()); fn(d); f.write_text(json.dumps(d))


def test_every_superpowers_check_fails_when_what_it_checks_is_broken(tmp_state, tmp_path, monkeypatch):
    arm, p = config.load_arm("superpowers"), Paths(PASS, "superpowers"); repo.init(p, "superpowers", PASS)
    assert not failing(run(p, arm)), "the vendored plugin passes every script check"
    backup = tmp_path / "backup"; shutil.copytree(p.base, backup, symlinks=True)
    clean = tmp_path / "plugins"; _export_plugins(p, arm, clean)
    root = "superpowers"

    def variant(name, fn):
        d = tmp_path / name; shutil.copytree(clean, d, symlinks=True); fn(d / root); return d
    cases = {
        "unmodified copy": (lambda r: None, set()),                               # the mount itself breaks nothing
        "version 6.4.1": (lambda r: _edit_json(r / ".claude-plugin/plugin.json", lambda d: d.update(version="6.4.1")),
                          {"superpowers.plugin-version"}),
        "no writing-plans skill": (lambda r: shutil.rmtree(r / "skills/writing-plans"), {"superpowers.skills"}),
        "no using-superpowers skill": (lambda r: shutil.rmtree(r / "skills/using-superpowers"), {"superpowers.skills"}),
        "no executing-plans skill": (lambda r: shutil.rmtree(r / "skills/executing-plans"), {"superpowers.skills"}),
        "no using-git-worktrees skill": (lambda r: shutil.rmtree(r / "skills/using-git-worktrees"), {"superpowers.skills"}),
        "no requesting-code-review skill": (lambda r: shutil.rmtree(r / "skills/requesting-code-review"),
                                            {"superpowers.skills"}),
        "no SessionStart hook": (lambda r: _edit_json(r / "hooks/hooks.json", lambda d: d["hooks"].pop("SessionStart")),
                                 {"superpowers.session-hook"}),
        "no session-start script": (lambda r: (r / "hooks/session-start").unlink(), {"superpowers.session-hook"}),
        "a second vendored plugin": (lambda r: shutil.copytree(r, r.parent / "other"), {"common.no-foreign-plugins"}),
    }
    seen = {n: failing(run(p, arm, extra=[Mount(variant(n.replace(" ", "-"), fn), "/opt/plugins", True)]))
            for n, (fn, _) in cases.items()}
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common)
    want = {n: w for n, (_, w) in cases.items()} | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("superpowers", want.values())


def test_superpowers_route_a_reads_the_installed_plugin_from_install_path(tmp_state, tmp_path, monkeypatch):  # OD9 A
    """T10 FR1 item 3: the root is installed_plugins.json's installPath for superpowers@claude-plugins-official;
    never `.`, never another cached version or marketplace."""
    arm, p = config.load_arm("superpowers"), Paths(PASS, "superpowers"); repo.init(p, "superpowers", PASS)
    clean = tmp_path / "plugins"; _export_plugins(p, arm, clean)
    cache = p.config_dir / "plugins" / "cache"
    for mkt, ver in (("claude-plugins-official", "6.4.2"), ("claude-plugins-official", "6.4.1"),
                     ("superpowers-marketplace", "6.4.2")):
        d = cache / mkt / "superpowers" / ver; shutil.copytree(clean / "superpowers", d)
        _edit_json(d / ".claude-plugin/plugin.json", lambda j, v=ver: j.update(version=v))
    ctr = f"{p.container_home}/.claude/plugins/cache"

    def installed(path, key="superpowers@claude-plugins-official"):
        return lambda: (p.config_dir / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {key: [{"scope": "user", "installPath": path}]}}))
    backup = tmp_path / "backup"; shutil.copytree(p.base, backup, symlinks=True)
    env = {"PLUGIN_ROUTE": "marketplace"}
    cases = {
        "the installed 6.4.2": (installed(f"{ctr}/claude-plugins-official/superpowers/6.4.2"), set(), env),
        "installed 6.4.1 beside a cached 6.4.2": (installed(f"{ctr}/claude-plugins-official/superpowers/6.4.1"),
                                                  {"superpowers.plugin-version"}, env),
        "installPath missing on disk": (installed(f"{ctr}/claude-plugins-official/superpowers/9.9.9"),
                                        {"superpowers.plugin-version", "superpowers.skills",
                                         "superpowers.session-hook"}, env),
        "installed from another marketplace": (installed(f"{ctr}/superpowers-marketplace/superpowers/6.4.2",
                                                         "superpowers@superpowers-marketplace"),
                                               {"superpowers.plugin-version", "superpowers.skills",
                                                "superpowers.session-hook"}, env),
        "no installed_plugins.json": (None, {"superpowers.plugin-version", "superpowers.skills",
                                             "superpowers.session-hook"}, env),
    }
    seen = run_breaks(monkeypatch, p, arm, backup, cases)
    assert seen == {n: w for n, (_, w, _) in cases.items()}
    fresh(monkeypatch, p, backup, "detail"); cases["the installed 6.4.2"][0]()
    got = run(p, arm, env=env)
    assert got["superpowers.plugin-version"].detail == f"{ctr}/claude-plugins-official/superpowers/6.4.2: 6.4.2"
    fresh(monkeypatch, p, backup, "none")
    got = run(p, arm, env=env)
    assert got["superpowers.plugin-version"].detail.startswith("<no installPath"), got["superpowers.plugin-version"]


# ---- 4. openspec: the real [setup] shell steps, offline, then each check broken in turn ------------------------
def test_openspec_setup_passes_its_checks_and_every_check_fails_when_broken(tmp_state, tmp_path, monkeypatch):
    arm, p = config.load_arm("openspec"), Paths(PASS, "openspec")
    got = {c.id: c for c in checklist.run_shell_only(PASS, "openspec", offline=True)}   # no network needed at all
    assert set(got) == script_only_ids("openspec") and not failing(got), [got[i] for i in failing(got)]
    assert (p.home / ".config" / "openspec" / "config.json").is_file()      # manifest path `~/.config/openspec`
    backup = tmp_path / "backup"; shutil.copytree(p.base, backup, symlinks=True)
    fake = tmp_path / "fakebin"; fake.mkdir()
    (fake / "openspec").write_text('#!/bin/sh\n[ "$1" = --version ] && { echo 1.13.1; exit 0; }\n'
                                   'exec /usr/local/bin/openspec "$@"\n')
    (fake / "openspec").chmod(0o755)

    def cfg(fn):
        return lambda: _edit_json(p.home / ".config/openspec/config.json", fn)

    def yaml(fn):
        def edit():
            f = p.repo / "openspec/config.yaml"        # resolved per case: each case has its own state root
            f.write_text(fn(f.read_text()))
        return edit
    principle = "Use the `eventsourcing` library for the event store and projection."
    cases = {
        "sync command missing": (lambda: (p.repo / ".claude/commands/opsx/sync.md").unlink(), {"openspec.commands"}),
        "explore skill missing": (lambda: shutil.rmtree(p.repo / ".claude/skills/openspec-explore"), {"openspec.skills"}),
        "no specs tree": (lambda: shutil.rmtree(p.repo / "openspec/specs"), {"openspec.tree"}),
        "no changes tree": (lambda: shutil.rmtree(p.repo / "openspec/changes"), {"openspec.tree"}),
        "another schema": (yaml(lambda t: t.replace("schema: spec-driven", "schema: my-schema")), {"openspec.tree"}),
        "telemetry on in config": (cfg(lambda d: d["telemetry"].update(enabled=True)), {"openspec.telemetry-off"}),
        "telemetry unset in config": (cfg(lambda d: d.pop("telemetry")), {"openspec.telemetry-off"}),
        "context with a changed principle": (yaml(lambda t: t.replace(principle, "Use SQLite for the event store.")),
                                             {"openspec.context"}),
        "context with an extra line": (yaml(lambda t: t + "  - Also: use Django.\n"), {"openspec.context"}),
        "no context": (yaml(lambda t: t[:t.index("\ncontext:")] + "\n"), {"openspec.context"}),
    }
    seen = {}
    for n, (name, (mutate, _)) in enumerate(cases.items()):
        fresh(monkeypatch, p, backup, n); mutate(); seen[name] = failing(run(p, arm))
    fresh(monkeypatch, p, backup, "env")
    seen["OPENSPEC_TELEMETRY=1"] = failing(run(p, arm, env={"OPENSPEC_TELEMETRY": "1"}))
    seen["openspec 1.13.1 on PATH"] = failing(run(p, arm, extra=[Mount(fake, "/fakebin", True)],
                                                  env={"PATH": f"/fakebin:{PATH}"}))
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common)
    seen["a plugin installed"] = run_breaks(monkeypatch, p, arm, backup, {"x": (lambda: (
        (p.config_dir / "plugins").mkdir(parents=True, exist_ok=True),
        (p.config_dir / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"plugins": {"superpowers@claude-plugins-official": []}}))), None, {})}, tag="pl")["x"]
    want = {n: w for n, (_, w) in cases.items()} | {"OPENSPEC_TELEMETRY=1": {"openspec.telemetry-off"},
                                                     "openspec 1.13.1 on PATH": {"openspec.version"},
                                                     "a plugin installed": {"common.no-foreign-plugins"}} \
        | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("openspec", want.values())


# ---- 5. bmad: PARKED — the script's logic against fixtures on the base image ----------------------------------
PEP723 = "# /// script\n# requires-python = \">=3.12\"\n# dependencies = []\n# ///\nprint(1)\n"


def _bmad_fixture(p: Paths, plugins: Path) -> None:
    for name in ("bmad-method", "bmad-core-tools"):
        (plugins / name / ".claude-plugin").mkdir(parents=True)
        (plugins / name / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name, "version": "6.12.0"}))
    b = p.repo / "_bmad"
    (b / "custom").mkdir(parents=True); (b / "scripts").mkdir(); (b / "core" / "scripts").mkdir(parents=True)
    (p.repo / "_bmad-output").mkdir()
    (b / "config.toml").write_text('[core]\noutput_folder = "_bmad-output"\n')
    (b / "custom" / "ticketing-store-config.toml").write_text(
        'description = "GitHub Issues through the gh CLI"\n[tickets]\nstore = "github"\nkey = ""\nrepo = ""\n')
    for f in (b / "scripts" / "setup_util.py", b / "core" / "scripts" / "memlog.py"):
        f.write_text(PEP723); Path(f"{f}.lock").write_text("version = 1\n")
    (b / "scripts" / "plain.py").write_text("print('no inline metadata, no lock needed')\n")


def test_every_bmad_check_fails_when_what_it_checks_is_broken_on_fixtures(tmp_state, tmp_path, monkeypatch):
    """Not the bmad image (PARKED): the base image, with the documented layout as fixtures. Ready for unparking."""
    base = config.load_pins().images["base"]
    real_image_for = gitops.image_for
    monkeypatch.setattr(gitops, "image_for", lambda a: base if a == "bmad" else real_image_for(a))
    arm, p = config.load_arm("bmad"), Paths(PASS, "bmad"); repo.init(p, "bmad", PASS)
    plugins = tmp_path / "plugins"; _bmad_fixture(p, plugins)
    mount = [Mount(plugins, "/opt/plugins", True)]
    got = run(p, arm, extra=mount)
    assert set(got) == script_only_ids("bmad") and not failing(got), [got[i] for i in failing(got)]
    backup, pbackup = tmp_path / "backup", tmp_path / "pbackup"
    shutil.copytree(p.base, backup, symlinks=True); shutil.copytree(plugins, pbackup)
    cur = {}                                                    # this case's own plugins dir (never re-mounted)

    def store():
        return p.repo / "_bmad/custom/ticketing-store-config.toml"

    def edit_store(a, b):
        return lambda: store().write_text(store().read_text().replace(a, b))
    cases = {
        "bmad-method 6.11.0": (lambda: _edit_json(cur["plugins"] / "bmad-method/.claude-plugin/plugin.json",
                                                  lambda d: d.update(version="6.11.0")), {"bmad.plugin-version"}, {}),
        "core tools missing": (lambda: shutil.rmtree(cur["plugins"] / "bmad-core-tools"),
                               {"bmad.plugin-version", "common.no-foreign-plugins"}, {}),
        "a foreign plugin": (lambda: shutil.copytree(cur["plugins"] / "bmad-method", cur["plugins"] / "superpowers"),
                             {"common.no-foreign-plugins"}, {}),
        "no _bmad/config.toml": (lambda: (p.repo / "_bmad/config.toml").unlink(), {"bmad.setup-done"}, {}),
        "no output folder": (lambda: (p.repo / "_bmad-output").rmdir(), {"bmad.setup-done"}, {}),
        "repo store": (edit_store('"github"', '"repo"'), {"bmad.ticketing-gh"}, {}),
        "no ticketing config": (lambda: store().unlink(), {"bmad.ticketing-gh"}, {}),
        "another repo": (edit_store('repo = ""', 'repo = "someone/else"'),
                         {"bmad.ticketing-gh"}, {"GH_REPO": "troupe-run/bakeoff-specs-bmad-pass1"}),
        "hub script unlocked": (lambda: Path(f"{p.repo}/_bmad/scripts/setup_util.py.lock").unlink(),
                                {"bmad.scripts-locked"}, {}),
        "module script unlocked": (lambda: Path(f"{p.repo}/_bmad/core/scripts/memlog.py.lock").unlink(),
                                   {"bmad.scripts-locked"}, {}),
        "no scripts at all": (lambda: shutil.rmtree(p.repo / "_bmad/scripts"), {"bmad.scripts-locked"}, {}),
        "the matching repo": (edit_store('repo = ""', 'repo = "troupe-run/bakeoff-specs-bmad-pass1"'),
                              set(), {"GH_REPO": "troupe-run/bakeoff-specs-bmad-pass1"}),     # accepted
    }
    seen = {}
    for n, (name, (mutate, _, env)) in enumerate(cases.items()):
        fresh(monkeypatch, p, backup, n)
        cur["plugins"] = tmp_path / f"plugins-{n}"; shutil.copytree(pbackup, cur["plugins"])
        mutate(); seen[name] = failing(run(p, arm, extra=[Mount(cur["plugins"], "/opt/plugins", True)], env=env))
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common, extra=lambda: [Mount(pbackup, "/opt/plugins", True)])
    want = {n: w for n, (_, w, _) in cases.items()} | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("bmad", want.values())


def test_bmad_real_image_checks_skip_while_parked():
    why = parked("bmad")
    if why is None:
        pytest.skip("bmad is no longer parked: the real-image tests above run instead")
    assert "PARKED" in why and "bmad" in why



# ---- 6. Task 11: speckit, speckitty (+ beads), ccsdd — the real [setup] shell steps offline, the agent turn's file
#         as a fixture, then every check broken in turn ----------------------------------------------------------
def fake_version(tmp_path: Path, name: str, argv: str, prints: str) -> list:
    """/fakebin/<name>: prints `prints` for exactly `<name> <argv>`, and runs the real /usr/local/bin/<name>
    otherwise (so only the version check can see it)."""
    d = tmp_path / f"fakebin-{name}"; d.mkdir()
    (d / name).write_text(f'#!/bin/sh\n[ "$*" = "{argv}" ] && {{ echo "{prints}"; exit 0; }}\n'
                          f'exec /usr/local/bin/{name} "$@"\n')
    (d / name).chmod(0o755)
    return [Mount(d, "/fakebin", True)]


def foreign_plugin(p: Paths):
    def mutate():
        (p.config_dir / "plugins").mkdir(parents=True, exist_ok=True)
        (p.config_dir / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"plugins": {"superpowers@claude-plugins-official": []}}))
    return mutate


def break_each(monkeypatch, p, arm, backup, cases) -> dict:
    """cases: name -> (mutate or None, want, env, extra mounts); each on its own never-mounted copy of `backup`."""
    seen = {}
    for n, (name, (mutate, _, env, extra)) in enumerate(cases.items()):
        fresh(monkeypatch, p, backup, f"t11-{n}")
        if mutate:
            mutate()
        seen[name] = failing(run(p, arm, extra=extra, env=env))
    return seen


def offline_setup_then_backup(arm_name: str, complete, tmp_path) -> tuple[config.Arm, Paths, Path, set[str]]:
    """The arm's real [setup] shell steps with an EMPTY egress allowlist (they need no network); only the agent turn's
    output is missing, and `complete` writes it as a fixture. Then every script check is green. Returns the arm, its
    paths, a backup of the post-setup state and the checks that failed BEFORE the fixture."""
    arm, p = config.load_arm(arm_name), Paths(PASS, arm_name)
    got = {c.id: c for c in checklist.run_shell_only(PASS, arm_name, offline=True)}
    assert set(got) == script_only_ids(arm_name)
    before = failing(got)
    complete(p)
    got = run(p, arm)
    assert not failing(got), [got[i] for i in failing(got)]
    backup = tmp_path / "backup"; shutil.copytree(p.base, backup, symlinks=True)
    return arm, p, backup, before


PRINCIPLES_TEXT = checklist.PRINCIPLES.read_text()


def _constitution(p: Paths) -> None:
    f = p.repo / ".specify/memory/constitution.md"
    (p.base.parent / "constitution-template.md").write_text(f.read_text())       # kept for the "template" case
    f.write_text("# Project Constitution\n\n" + PRINCIPLES_TEXT)


def test_speckit_setup_passes_its_checks_and_every_check_fails_when_broken(tmp_state, tmp_path, monkeypatch):
    arm, p, backup, before = offline_setup_then_backup("speckit", _constitution, tmp_path)
    assert before == {"speckit.constitution"}        # init leaves the template: red until the agent turn has run
    template = (tmp_path / "state" / PASS / "constitution-template.md").read_text()

    def registry(fn):
        return lambda: _edit_json(p.repo / ".specify/extensions/.registry", fn)
    none = ({}, [])
    cases = {
        "constitution is the template": (lambda: (p.repo / ".specify/memory/constitution.md").write_text(template),
                                         {"speckit.constitution"}, *none),
        "constitution empty": (lambda: (p.repo / ".specify/memory/constitution.md").write_text(""),
                               {"speckit.constitution"}, *none),
        "a placeholder left": (lambda: (p.repo / ".specify/memory/constitution.md").write_text(
            "# Constitution\n\nRatified: [RATIFICATION_DATE]\n"), {"speckit.constitution"}, *none),
        "no converge skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/speckit-converge"), {"speckit.skills"}, *none),
        "no taskstoissues skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/speckit-taskstoissues"),
                                   {"speckit.skills"}, *none),
        "no constitution skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/speckit-constitution"),
                                  {"speckit.skills"}, *none),
        "no bug-fix skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/speckit-bug-fix"), {"speckit.bug-skills"}, *none),
        "bug extension disabled": (registry(lambda d: d["extensions"]["bug"].update(enabled=False)),
                                   {"speckit.bug-skills"}, *none),
        "bug extension unregistered": (registry(lambda d: d["extensions"].pop("bug")), {"speckit.bug-skills"}, *none),
        "specify 1.0.11 on PATH": (None, {"speckit.version"}, {"PATH": f"/fakebin:{PATH}"},
                                   fake_version(tmp_path, "specify", "version", "│     CLI Version    1.0.11     │")),
        "a plugin installed": (foreign_plugin(p), {"common.no-foreign-plugins"}, *none),
    }
    seen = break_each(monkeypatch, p, arm, backup, cases)
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common)
    want = {n: w for n, (_, w, _, _) in cases.items()} | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("speckit", want.values())


def _charter(p: Paths) -> None:
    d = p.repo / ".kittify/charter"; d.mkdir(parents=True)
    (d / "charter.md").write_text("# Charter\n\n" + PRINCIPLES_TEXT)
    (d / "charter.yaml").write_text("schema_version: 1\nprinciples: see charter.md\n")


def _kittify_tracker(p: Paths, fn):
    """Edit the `tracker:` block of .kittify/config.yaml as text (a YAML round trip would reorder it)."""
    def edit():
        f = p.repo / ".kittify/config.yaml"
        f.write_text(fn(f.read_text()))
    return edit


def _drop_hook(p: Paths, command_re: str):
    import re as _re

    def edit():
        f = p.repo / ".claude/settings.json"
        d = json.loads(f.read_text())
        d["hooks"]["SessionStart"] = [e for e in d["hooks"]["SessionStart"]
                                      if not any(_re.search(command_re, h.get("command", "")) for h in e.get("hooks", []))]
        f.write_text(json.dumps(d))
    return edit


_OPT_IN = """/opt/venvs/speckitty/bin/python -c 'from pathlib import Path
from specify_cli.sync.routing import resolve_checkout_sync_routing_readonly
from specify_cli.sync.consent import record_project_opt_in
r = resolve_checkout_sync_routing_readonly(Path("."))
record_project_opt_in(str(r.project_uuid), actor="falsification-test")'"""


def _in_arm(p: Paths, arm: config.Arm, cmd: str):
    """A mutation that has to run as the tool itself: the arm image, network none, home and work writable."""
    def run_it():
        r = docker.run(checklist.arm_spec(p, arm, ["bash", "-c", cmd], ro=False, name="mutate"), timeout=300)
        assert r.returncode == 0, r.stderr.decode()[-500:]
    return run_it


def _tamper(p: Paths, rel: str):
    """spec-kitty installs its managed files read-only; a hand edit makes it writable first."""
    def edit():
        f = p.repo / rel
        f.chmod(0o644); f.write_text(f.read_text() + "\ntampered\n")
    return edit


def test_speckitty_setup_passes_its_checks_and_every_check_fails_when_broken(tmp_state, tmp_path, monkeypatch):
    arm, p, backup, before = offline_setup_then_backup("speckitty", _charter, tmp_path)
    assert before == {"speckitty.charter"}           # red until the agent turn has run
    none = ({}, [])
    cases = {
        "no charter.yaml": (lambda: (p.repo / ".kittify/charter/charter.yaml").unlink(), {"speckitty.charter"}, *none),
        "empty charter.md": (lambda: (p.repo / ".kittify/charter/charter.md").write_text(""), {"speckitty.charter"}, *none),
        # verify-setup reinstalls a missing /spec-kitty.* command; on the read-only verify mounts that write is refused,
        # so it fails too. Measured limits, recorded as cases so they stay visible: it does NOT notice a deleted managed
        # skill (repo or user scope) nor a managed file whose content was changed
        "no /spec-kitty.accept": (lambda: (p.config_dir / "commands/spec-kitty.accept.md").unlink(),
                                  {"speckitty.commands", "speckitty.verify-setup"}, *none),
        "no /spec-kitty.charter": (lambda: (p.config_dir / "commands/spec-kitty.charter.md").unlink(),
                                   {"speckitty.commands", "speckitty.verify-setup"}, *none),
        "a managed skill deleted (not noticed)": (lambda: (p.repo / ".claude/skills/spec-kitty-runtime-next/SKILL.md").unlink(),
                                                  set(), *none),
        "a managed skill's content changed (not noticed)": (_tamper(p, ".claude/skills/spec-kitty-runtime-next/SKILL.md"), set(), *none),
        "spec-kitty's SessionStart hook dropped": (_drop_hook(p, r"^spec-kitty session-start"),
                                                  {"speckitty.session-hook"}, *none),
        "bd prime hook dropped": (_drop_hook(p, r"^bd prime"), {"beads.claude-hook"}, *none),
        "bound to fp": (_kittify_tracker(p, lambda t: t.replace("provider: beads", "provider: fp")),
                        {"speckitty.tracker-binding"}, *none),
        "another workspace": (_kittify_tracker(p, lambda t: t.replace("workspace: beads", "workspace: other")),
                              {"speckitty.tracker-binding"}, *none),
        "egress refused": (_kittify_tracker(p, lambda t: t.replace("egress: permitted", "egress: refused")),
                           {"speckitty.tracker-egress"}, *none),
        "egress not recorded": (_kittify_tracker(p, lambda t: t.replace("  egress: permitted\n", "")),
                                {"speckitty.tracker-egress"}, *none),
        "egress a near-miss spelling": (_kittify_tracker(p, lambda t: t.replace("egress: permitted", "egress: Permitted")),
                                        {"speckitty.tracker-egress"}, *none),
        # FR1 item 2: hosted-sync consent granted through spec-kitty's own "only action that may create a local
        # hosted-sync grant" (record_project_opt_in; `spec-kitty sync opt-in` refuses offline on a fresh project store)
        "hosted-sync consent granted": (_in_arm(p, arm, _OPT_IN), {"speckitty.hosted-egress-refused"}, *none),
        "no beads database": (lambda: shutil.rmtree(p.repo / ".beads/embeddeddolt"), {"beads.init"}, *none),
        "no beads config": (lambda: (p.repo / ".beads/config.yaml").unlink(), {"beads.init"}, *none),
        "beads metrics on": (lambda: (p.home / ".config/bd/config.yaml").write_text(
            (p.home / ".config/bd/config.yaml").read_text().replace("disabled: true", "disabled: false")),
                             {"beads.metrics-off"}, *none),
        "spec-kitty 3.2.7rc1 on PATH": (None, {"speckitty.version"}, {"PATH": f"/fakebin:{PATH}"},
                                        fake_version(tmp_path, "spec-kitty", "--version", "spec-kitty-cli version 3.2.7rc1")),
        "bd 1.3.1 on PATH": (None, {"beads.version"}, {"PATH": f"/fakebin:{PATH}"},
                             fake_version(tmp_path, "bd", "version", "bd version 1.3.1 (0000000: HEAD@0000000)")),
        "a plugin installed": (foreign_plugin(p), {"common.no-foreign-plugins"}, *none),
    }
    seen = break_each(monkeypatch, p, arm, backup, cases)
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common)
    want = {n: w for n, (_, w, _, _) in cases.items()} | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("speckitty", want.values())


def test_speckitty_setup_leaves_bd_inits_commit_a_local_dolt_remote_and_both_tools_hooks(tmp_state, tmp_path, monkeypatch):
    """What setup leaves beside the checks: bd init's own commit as the neutral identity, beads' Dolt remote on the
    local origin only, and spec-kitty's hooks and bd's hook side by side in the one project settings file."""
    offline_setup_then_backup("speckitty", _charter, tmp_path)
    p = Paths(PASS, "speckitty")
    log = gitops.git(p, "log", "--format=%an <%ae>|%s").stdout.decode().splitlines()
    assert "Developer <developer@troupe.run>|bd init: initialize beads issue tracking" in log
    assert "sync.remote: \"/home/actor/origin.git\"" in (p.repo / ".beads/config.yaml").read_text()
    hooks = json.loads((p.repo / ".claude/settings.json").read_text())["hooks"]
    starts = [h["command"] for e in hooks["SessionStart"] for h in e["hooks"]]
    assert "spec-kitty session-start" in starts and any(c.startswith("bd prime") for c in starts)
    assert [h["command"] for e in hooks["Stop"] for h in e["hooks"]] == ["spec-kitty session-stop"]


def _steering(p: Paths) -> None:
    d = p.repo / ".kiro/steering"; d.mkdir(parents=True)
    (d / "product.md").write_text("# Product\n\n" + PRINCIPLES_TEXT)


def test_ccsdd_setup_passes_its_checks_and_every_check_fails_when_broken(tmp_state, tmp_path, monkeypatch):
    arm, p, backup, before = offline_setup_then_backup("ccsdd", _steering, tmp_path)
    assert before == {"ccsdd.steering"}              # red until the agent turn has run
    none = ({}, [])

    def claude_md(fn):
        return lambda: (p.repo / "CLAUDE.md").write_text(fn((p.repo / "CLAUDE.md").read_text()))
    cases = {
        "no kiro-validate-impl skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/kiro-validate-impl"),
                                        {"ccsdd.skills"}, *none),
        "no kiro-discovery skill": (lambda: shutil.rmtree(p.repo / ".claude/skills/kiro-discovery"), {"ccsdd.skills"}, *none),
        "an 18th kiro skill": (lambda: shutil.copytree(p.repo / ".claude/skills/kiro-impl", p.repo / ".claude/skills/kiro-extra"),
                               {"ccsdd.skills"}, *none),
        "no steering templates": (lambda: shutil.rmtree(p.repo / ".kiro/settings/templates/steering"), {"ccsdd.settings"}, *none),
        "no spec templates": (lambda: shutil.rmtree(p.repo / ".kiro/settings/templates/specs"), {"ccsdd.settings"}, *none),
        "no CLAUDE.md": (lambda: (p.repo / "CLAUDE.md").unlink(), {"ccsdd.project-memory"}, *none),
        "CLAUDE.md without the kiro paths": (claude_md(lambda t: t.replace(".kiro/", "docs/")), {"ccsdd.project-memory"}, *none),
        "no steering": (lambda: shutil.rmtree(p.repo / ".kiro/steering"), {"ccsdd.steering"}, *none),
        "an empty steering file": (lambda: (p.repo / ".kiro/steering/tech.md").write_text(""), {"ccsdd.steering"}, *none),
        "legacy command mode": (lambda: (p.repo / ".claude/commands/kiro").mkdir(parents=True), {"ccsdd.no-legacy"}, *none),
        "cc-sdd 3.0.0 on PATH": (None, {"ccsdd.version"}, {"PATH": f"/fakebin:{PATH}"},
                                 fake_version(tmp_path, "cc-sdd", "--version", "cc-sdd v3.0.0")),
        "a plugin installed": (foreign_plugin(p), {"common.no-foreign-plugins"}, *none),
    }
    seen = break_each(monkeypatch, p, arm, backup, cases)
    common = common_breaks(p)
    seen |= run_breaks(monkeypatch, p, arm, backup, common)
    want = {n: w for n, (_, w, _, _) in cases.items()} | {n: w for n, (_, w, _) in common.items()}
    assert seen == want
    assert_every_script_id_falsified("ccsdd", want.values())



# ---- 7. Task 11 fix round 1 -------------------------------------------------------------------------------------
def test_speckitty_setup_commit_and_origin_push_succeed_with_the_beads_hooks_active(tmp_state):
    """FR1 item 1: after speckitty's real shell steps (bd init: core.hooksPath=.beads/hooks, a Dolt remote on origin),
    the runner's own setup commit and `setup.origin-push` run through gitops' write containers (network none,
    GIT_CONFIG_GLOBAL=/dev/null, hooks ON) and both succeed."""
    p = Paths(PASS, "speckitty")
    checklist.run_shell_only(PASS, "speckitty", offline=True)
    cfg = (p.repo / ".git/config").read_text()
    assert f"hookspath = {p.container_repo}/.beads/hooks" in cfg.lower()          # the beads hooks are live
    assert {"pre-commit", "pre-push"} <= {f.name for f in (p.repo / ".beads/hooks").iterdir()}
    assert 'sync.remote: "/home/actor/origin.git"' in (p.repo / ".beads/config.yaml").read_text()
    assert gitops.state(p).dirty
    sha = gitops.commit_all(p, gitops.IDENTITY, "Set up spec-kitty/spec-kitty 3.2.7")
    assert not gitops.state(p).dirty
    c = checklist._origin_push(p)
    assert c.ok, c
    remote = gitops.git(p, "ls-remote", gitops.ORIGIN, "refs/heads/main", write=True).stdout.decode().split()
    assert remote and remote[0] == sha


def _two_offline_manifests(arm_name: str, tmp_path, monkeypatch) -> tuple[dict, dict]:
    from runner import paths
    out = []
    for n in (1, 2):
        monkeypatch.setattr(paths, "STATE", tmp_path / f"setup-{n}")
        checklist.run_shell_only(PASS, arm_name, offline=True)
        out.append(checklist.manifest_full(Paths(PASS, arm_name), config.load_arm(arm_name)))
    (a, ma), (b, mb) = out
    assert ma == mb == []                                        # every listed manifest path is created by setup
    return a, b


@pytest.mark.parametrize("arm", ["speckit", "speckitty", "ccsdd"])
def test_volatile_paths_are_exactly_what_differs_between_two_offline_setups(arm, tmp_state, tmp_path, monkeypatch):
    """FR1 item 6 guard: every `install-stamp` entry really differs between two identical offline setups (so the list
    cannot quietly hide a real difference), and nothing else differs (so pass 2 of an unchanged setup is green)."""
    a, b = _two_offline_manifests(arm, tmp_path, monkeypatch)
    home = Paths(PASS, arm).container_home
    vol = config.load_arm(arm).volatile_paths
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    for v in (v for v in vol if v.kind == "install-stamp"):
        assert any(checklist.is_volatile(k, [v.path], home) for k in differing), f"{v.path} never differs: {v.why}"
    assert {k for k in differing if not checklist.is_volatile(k, [v.path for v in vol], home)} == set()
