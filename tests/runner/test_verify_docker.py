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


@pytest.mark.parametrize("arm", ["control", "superpowers", "openspec", "bmad"])
def test_step_mode_prints_only_the_common_checks_and_the_version(arm, tmp_state):
    skip_if_parked(arm)
    p = Paths(PASS, arm); repo.init(p, arm, PASS)
    got = {c.id for c in checklist.verify(p, config.load_arm(arm), "step")}
    common = {"common.claude-version", "common.isolation-env", "common.git-identity", "common.no-foreign-plugins",
              "common.origin"}
    assert got == common | ({f"{arm}.plugin-version"} if arm in ("superpowers", "bmad") else set()) \
        | ({"openspec.version"} if arm == "openspec" else set())


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
