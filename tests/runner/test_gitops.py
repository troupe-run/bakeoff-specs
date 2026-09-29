"""Host-side git helpers (review B2): `ls_remote_tag` resolves a plugin's pinned tag to a commit SHA
before any arm image exists. Task 8 extends `runner/gitops.py` with the in-container helpers."""
import subprocess
import pytest
from runner import gitops


class FakeCompleted:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_ls_remote_tag_prefers_the_peeled_commit_of_an_annotated_tag(monkeypatch):
    def fake_run(argv, **kw):
        assert argv == ["git", "ls-remote", "--tags", "https://github.com/obra/superpowers"]
        return FakeCompleted("668b16d4d8d4d603fd257567684fbbffccbf2022\trefs/tags/v6.4.2\n"
                              "8ca22dba9a94f28898bbce59f2537ff4d87c747d\trefs/tags/v6.4.2^{}\n"
                              "deadbeef00000000000000000000000000000000\trefs/tags/v6.4.1\n")
    monkeypatch.setattr(gitops.subprocess, "run", fake_run)
    assert gitops.ls_remote_tag("obra/superpowers", "v6.4.2") == "8ca22dba9a94f28898bbce59f2537ff4d87c747d"


def test_ls_remote_tag_returns_the_lightweight_tag_commit_directly(monkeypatch):
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted("abc123\trefs/tags/v1.0.0\n"))
    assert gitops.ls_remote_tag("x/y", "v1.0.0") == "abc123"


def test_ls_remote_tag_raises_when_the_remote_has_no_such_tag(monkeypatch):
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted(""))
    with pytest.raises(gitops.TagNotFound, match="v6.12.0"):
        gitops.ls_remote_tag("bmad-code-org/bmad-plugins", "v6.12.0")


def test_ls_remote_tag_raises_git_remote_unavailable_not_tag_not_found_when_git_itself_fails(monkeypatch):
    """review fix-round-1 item 3: a nonzero exit from `git ls-remote` (network unreachable, repo not
    found, DNS failure, ...) means we couldn't even ask the question — that's a transient/environment
    failure, fatal, and must never be treated as 'this tag doesn't exist' (which parks the plugin)."""
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted("", returncode=128, stderr="boom"))
    with pytest.raises(gitops.GitRemoteUnavailable, match="boom"):
        gitops.ls_remote_tag("x/y", "v1.0.0")


def test_ls_remote_tag_raises_git_remote_unavailable_when_the_subprocess_call_itself_raises(monkeypatch):
    def raiser(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=30)
    monkeypatch.setattr(gitops.subprocess, "run", raiser)
    with pytest.raises(gitops.GitRemoteUnavailable):
        gitops.ls_remote_tag("x/y", "v1.0.0")


def test_git_remote_unavailable_is_not_a_tag_not_found():                  # they must not be confused
    assert not issubclass(gitops.GitRemoteUnavailable, gitops.TagNotFound)
    assert not issubclass(gitops.TagNotFound, gitops.GitRemoteUnavailable)


def test_host_env_disables_interactive_credential_prompts():
    env = gitops._host_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.network
def test_ls_remote_tag_resolves_superpowers_v6_4_2_for_real():
    assert gitops.ls_remote_tag("obra/superpowers", "v6.4.2") == "8ca22dba9a94f28898bbce59f2537ff4d87c747d"


@pytest.mark.network
def test_bmad_plugins_repo_has_no_v6_12_0_tag_so_bmad_is_parked():
    """Evidence for B2: `bmad-code-org/bmad-plugins` (the repo CANDIDATES.md documents for the Claude Code
    plugin install) carries no tags at all — confirmed 2026-09-29 via `git ls-remote --tags` (empty) and a
    `git ls-remote` of all refs (only `main`, `core-tools-rename`, and PR refs). The plan's draft coordinates
    (tag `v6.12.0`, subdirs `plugins/bmad-method` / `plugins/bmad-core-tools`) do not exist on this repo;
    see task-3-report.md for the full finding."""
    with pytest.raises(gitops.TagNotFound):
        gitops.ls_remote_tag("bmad-code-org/bmad-plugins", "v6.12.0")


# --- Task 8: every git command on an arm repo runs in a network-less container (review S-1) -----------------
import ast
import re
from pathlib import Path
from runner import cli, repo
from runner.paths import Paths

RUNNER = Path(__file__).resolve().parents[2] / "runner"


def test_git_runs_in_a_networkless_container_of_the_arms_image():
    s = gitops.spec(Paths("pass1", "speckitty"), ["status", "--porcelain"])
    assert s.network == "none" and s.image == "bakeoff-arm-speckitty:1" and not s.proxy
    assert s.cmd[:3] == ["git", "-C", "/work/bakeoff-specs-speckitty"]


def test_a_dry_arm_runs_git_in_the_dryrun_image():
    assert gitops.spec(Paths("dry1", "dryrun"), ["status"]).image == "bakeoff-arm-dryrun:1"


def test_reads_mount_the_work_tree_read_only_and_ignore_global_config():
    s = gitops.spec(Paths("pass1", "control"), ["status"])
    assert [(m.ctr, m.ro) for m in s.mounts] == [("/work", True)]
    assert s.env["GIT_CONFIG_NOSYSTEM"] == "1" and s.env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    for flag in ["core.hooksPath=/dev/null", "core.fsmonitor=false", "safe.directory=*"]:
        assert flag in s.cmd


def test_writes_mount_work_read_write_and_keep_hooks():
    s = gitops.spec(Paths("pass1", "control"), ["commit", "-m", "x"], write=True)
    assert any(m.ctr == "/work" and not m.ro for m in s.mounts)
    assert any(m.ctr == "/home/actor" and not m.ro for m in s.mounts)      # the bare origin lives in home (B4)
    assert "core.hooksPath=/dev/null" not in s.cmd


def test_git_containers_carry_the_exact_bakeoff_run_label_so_sweep_finds_them():
    s = gitops.spec(Paths("pass1", "control"), ["status"])
    assert s.label == "bakeoff.run=pass1/control" and s.name.startswith("bk-git-pass1-control-")
    assert s.name != gitops.spec(Paths("pass1", "control"), ["status"]).name   # no fixed-name collision (m13)


def test_one_neutral_identity_for_every_arm():                                # review G9
    assert gitops.IDENTITY == ("Developer", "developer@troupe.run")
    assert gitops.TEAMMATE == ("Sam Teammate", "sam.teammate@troupe.run")


_GIT_ARGV = re.compile(r"""[\[(]\s*["']git["']\s*,""")


def test_no_runner_module_but_gitops_builds_a_git_argv():                     # review S-1
    offenders = [f.name for f in RUNNER.glob("*.py") if f.name != "gitops.py" and _GIT_ARGV.search(f.read_text())]
    assert offenders == []


HOST_HELPERS = {"ls_remote_tag", "commit_harness_file", "harness_is_clean", "clone_bundle_bare", "push_from_bare"}


def test_host_side_git_lives_only_in_helpers_that_never_take_an_arm_repo():   # review S-1
    """Inside gitops.py a `["git", ...]` argv may appear only in the named host helpers (public remotes,
    the harness repo, or a bare clone of a container-made bundle) — none of which accepts an arm's `Paths`.
    Everything else builds its argv through `spec()`, i.e. a container."""
    tree = ast.parse((RUNNER / "gitops.py").read_text())
    with_git = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, (ast.List, ast.Tuple)) and node.elts and \
                    isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "git":
                with_git.add(fn.name)
    assert with_git - {"spec"} == HOST_HELPERS
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in HOST_HELPERS]:
        assert all(not (a.annotation is not None and "Paths" in ast.unparse(a.annotation)) for a in fn.args.args), fn.name


class _Rec:
    """Stands in for docker.run: records each RunSpec, answers like a successful git."""
    def __init__(self, stdout=b"0123abcd\n"):
        self.specs, self.stdout = [], stdout

    def __call__(self, s, input=None, timeout=None):
        self.specs.append(s)
        return subprocess.CompletedProcess(s.cmd, 0, self.stdout, b"")


def _git_args(s):
    """argv after `git -C <repo> -c k=v ...`."""
    cmd = s.cmd[3:]
    while cmd and cmd[0] == "-c":
        cmd = cmd[2:]
    return cmd


def test_init_repo_creates_a_local_bare_origin_and_pushes_main_upstream(monkeypatch):     # preflight B4
    rec = _Rec()
    monkeypatch.setattr(gitops.docker, "run", rec)
    gitops.init_repo(Paths("pass1", "control"))
    argvs = [_git_args(s) for s in rec.specs]
    assert ["init", "-q", "-b", "main"] in argvs
    assert ["init", "-q", "--bare", "-b", "main", "/home/actor/origin.git"] in argvs
    assert ["remote", "add", "origin", "/home/actor/origin.git"] in argvs
    assert ["push", "-q", "-u", "origin", "main"] in argvs
    assert gitops.ORIGIN == "/home/actor/origin.git"
    assert all(s.network == "none" for s in rec.specs)
    assert not any("github.com" in a for s in rec.specs for a in s.cmd)      # the GitHub URL is never origin


def test_init_repo_takes_no_remote_url():                                      # preflight B4
    import inspect
    assert list(inspect.signature(gitops.init_repo).parameters) == ["p"]


def test_writes_never_sign_so_an_arms_gpg_program_cannot_break_a_harness_commit():
    s = gitops.spec(Paths("pass1", "control"), ["commit"], write=True)
    assert "commit.gpgsign=false" in s.cmd


def test_github_plan_prints_private_repos_and_runs_nothing(monkeypatch):     # strengthened (review Q-11)
    def boom(*a, **k): raise AssertionError("github_plan ran a command")
    monkeypatch.setattr(repo.subprocess, "run", boom)
    monkeypatch.setattr(gitops.subprocess, "run", boom)
    cmds = repo.github_plan("pass1")
    assert len(cmds) == 7 and all(c.startswith("gh repo create troupe-run/bakeoff-specs-") and "--private" in c for c in cmds)


def test_pass2_uses_the_scored_repo_name_and_other_passes_have_none():
    assert repo.github_slug("pass2", "openspec") == "troupe-run/bakeoff-specs-openspec"
    assert repo.github_slug("pass1", "openspec") == "troupe-run/bakeoff-specs-openspec-pass1"
    assert repo.github_slug("dry1", "dryrun") is None
    assert repo.github_slug("canary", "control") == "troupe-run/bakeoff-specs-control-canary"


def test_repo_github_slug_is_the_config_single_source():
    from runner import config
    assert repo.github_slug is config.github_slug


def test_verify_fails_when_any_troupe_run_repo_is_public(monkeypatch):     # review G7
    def fake(argv, **k):
        if argv[:3] == ["gh", "repo", "list"]:
            return type("R", (), {"returncode": 0, "stdout": '[{"name": "leaky"}]', "stderr": ""})()
        return type("R", (), {"returncode": 0, "stderr": "",
                              "stdout": '{"visibility": "PRIVATE", "hasIssuesEnabled": true, "isEmpty": true}'})()
    monkeypatch.setattr(repo.subprocess, "run", fake)
    res = repo.github_verify("pass1")
    assert res["_public_repos"] == ["leaky"] and not repo.verify_ok(res)


def test_verify_passes_only_when_every_repo_is_private_empty_with_issues(monkeypatch):
    def fake(argv, **k):
        if argv[:3] == ["gh", "repo", "list"]:
            return type("R", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stderr": "",
                              "stdout": '{"visibility": "PRIVATE", "hasIssuesEnabled": true, "isEmpty": true}'})()
    monkeypatch.setattr(repo.subprocess, "run", fake)
    assert repo.verify_ok(repo.github_verify("pass1"))


def test_cli_github_plan_prints_the_creates_and_pat_instructions_for_github_tracker_arms(capsys):
    assert cli.main(["github-plan", "pass1"]) == 0
    out = capsys.readouterr().out
    assert out.count("gh repo create") == 7
    assert "bakeoff-gh-pass1-control" in out and "expiration: 45 days" in out
    assert "bakeoff-gh-pass1-speckitty" not in out                       # beads tracker: no PAT


def test_cli_github_verify_exits_nonzero_unless_verify_ok(monkeypatch, capsys):
    monkeypatch.setattr(repo, "github_verify", lambda pass_: {"_public_repos": ["leaky"]})
    assert cli.main(["github-verify", "pass1"]) != 0
    monkeypatch.setattr(repo, "github_verify", lambda pass_: {"_public_repos": []})
    assert cli.main(["github-verify", "pass1"]) == 0


def test_cli_publish_refuses_while_there_is_no_secret_scanner(monkeypatch, capsys):   # S-2 lands in Task 21
    import importlib.util
    if importlib.util.find_spec("runner.secrets") is not None:
        pytest.skip("runner.secrets exists; publish is wired to it")
    monkeypatch.setattr(repo, "publish", lambda *a, **k: (_ for _ in ()).throw(AssertionError("published")))
    assert cli.main(["publish", "pass1", "control"]) != 0
    assert "secret scan" in capsys.readouterr().out


# --- fix round 1 ----------------------------------------------------------------------------------------

def test_the_host_never_untars_or_tars_an_arm_tree():                        # fix round 1, items 1+2
    """snapshot/restore/export/publish extraction runs `tar` in containers; no runner module uses tarfile
    (CPython's filter="data" has had bypasses, and it rejects the absolute links a venv contains)."""
    offenders = [f.name for f in RUNNER.glob("*.py") if re.search(r"\btarfile\b|extractall", f.read_text())]
    assert offenders == []


def test_harness_python_is_a_patched_interpreter():                           # fix round 1, item 2
    root = RUNNER.parent
    import tomllib
    assert tomllib.loads((root / "pyproject.toml").read_text())["project"]["requires-python"] == ">=3.12.11"
    pinned = tuple(int(x) for x in (root / ".python-version").read_text().strip().split("."))
    assert pinned >= (3, 12, 11)
    import sys
    assert sys.version_info[:3] >= (3, 12, 11)


def test_check_bundle_accepts_only_a_regular_file_with_a_bundle_header(tmp_path):     # fix round 1, item 4
    ok2, ok3 = tmp_path / "v2.bundle", tmp_path / "v3.bundle"
    ok2.write_bytes(b"# v2 git bundle\nabc refs/heads/main\n\n"); ok3.write_bytes(b"# v3 git bundle\n@object-format=sha1\n")
    gitops.check_bundle(ok2); gitops.check_bundle(ok3)
    bad = tmp_path / "bad.bundle"; bad.write_bytes(b"[core]\n\tfsmonitor = evil\n")
    link = tmp_path / "link.bundle"; link.symlink_to(ok2)
    d = tmp_path / "dir.bundle"; d.mkdir()
    for b in (bad, link, d, tmp_path / "missing.bundle"):
        with pytest.raises(ValueError):
            gitops.check_bundle(b)
    with pytest.raises(ValueError):
        gitops.clone_bundle_bare(bad, tmp_path / "clone.git")          # validated before host git reads it
    assert not (tmp_path / "clone.git").exists()


def test_log_parses_exactly_whatever_the_subject_or_author_contains(monkeypatch):    # fix round 1, item 5
    a, b = "a" * 40, "b" * 40
    rec = _Rec(stdout=f"{a}\0Eve \x1f Doe\0sub\x1fject\x1e\n\0{b}\0Bob\0plain\0".encode())
    monkeypatch.setattr(gitops.docker, "run", rec)
    assert gitops.log(Paths("pass1", "control"), "x", "y") == [
        {"sha": a, "author": "Eve \x1f Doe", "subject": "sub\x1fject\x1e\n"},
        {"sha": b, "author": "Bob", "subject": "plain"}]
    assert "-z" in _git_args(rec.specs[0])


def test_commits_between_records_split_exactly_even_with_separators_in_messages(monkeypatch):
    a, b = "a" * 40, "b" * 40
    rec = _Rec(stdout=f"{a}\0Fix \x1e alias\n\nbody \x1f x\n\0{b}\0Second\n\0".encode())
    monkeypatch.setattr(gitops.docker, "run", rec)
    out = gitops.commits_between(Paths("pass1", "control"), "x", "y")
    recs = [r.split("\x1f", 1) for r in out.split("\x1e") if r]
    assert recs == [[a, "Fix \ufffd alias\n\nbody \ufffd x"], [b, "Second"]]


def test_grep_passes_the_pattern_as_an_expression_not_an_option(monkeypatch):      # fix round 1, item 6
    rec = _Rec(stdout=b"")
    monkeypatch.setattr(gitops.docker, "run", rec)
    gitops.grep_files(Paths("pass1", "control"), "HEAD", "--open-files-in-pager=sh")
    args = _git_args(rec.specs[0])
    i = args.index("-e")
    assert args[i + 1] == "--open-files-in-pager=sh" and args.index("--") > i + 1


def _fake_restore(monkeypatch, fail_on=None):
    """Stand in for the tar container: write a recognisable tree into the staging mount."""
    from runner import repo as r
    def fake_run(s, what):
        if fail_on == "extract":
            raise RuntimeError("tar refused")
        out = next(m.host for m in s.mounts if m.ctr == "/out")
        for n in ("home", "work"):
            (out / n).mkdir(); (out / n / "restored").write_text(n)
    monkeypatch.setattr(r, "_run", fake_run)
    monkeypatch.setattr(r, "_await_visible_in_containers", lambda p: None)


def _live_tree(tmp_state):
    p = Paths("dry9", "dryrun")
    for d in (p.home, p.work, p.snapshots):
        d.mkdir(parents=True)
    (p.home / "current").write_text("h"); (p.work / "current").write_text("w")
    (p.snapshots / "step-01.tar").write_bytes(b"x")
    return p


def test_restore_swaps_in_the_extracted_trees_and_leaves_nothing_behind(tmp_state, monkeypatch):   # item 7
    p = _live_tree(tmp_state); _fake_restore(monkeypatch)
    repo.restore(p, 1)
    assert (p.home / "restored").exists() and (p.work / "restored").exists() and not (p.home / "current").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_a_failed_extract_leaves_the_current_trees_untouched(tmp_state, monkeypatch):
    p = _live_tree(tmp_state); _fake_restore(monkeypatch, fail_on="extract")
    with pytest.raises(RuntimeError):
        repo.restore(p, 1)
    assert (p.home / "current").exists() and (p.work / "current").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_a_failure_mid_swap_puts_the_previous_trees_back(tmp_state, monkeypatch):
    p = _live_tree(tmp_state); _fake_restore(monkeypatch)
    real = Path.rename
    def flaky(self, target):
        if self.name == "work" and self.parent.name.startswith(".restore-"):
            raise OSError("disk full")                            # the second move-in fails
        return real(self, target)
    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(OSError):
        repo.restore(p, 1)
    assert (p.home / "current").exists() and (p.work / "current").exists()
    assert not (p.home / "restored").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_restore_wait_is_bounded(tmp_state, monkeypatch):                    # item 8
    from runner import repo as r
    p = _live_tree(tmp_state)
    clock = iter(range(0, 1000, 10))
    monkeypatch.setattr(r.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(r.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(r.docker, "run", lambda s, timeout=None, input=None:
                        calls.append(timeout) or subprocess.CompletedProcess([], 1, b"", b""))
    with pytest.raises(RuntimeError, match="not visible"):
        r._await_visible_in_containers(p, timeout=30)
    assert calls and all(t == r.PROBE_SECONDS for t in calls) and len(calls) <= 5
    assert not [x for x in p.work.iterdir() if x.name.startswith(".bk-restored-")]


# --- fix round 2 ----------------------------------------------------------------------------------------

def test_log_keeps_an_empty_last_subject_and_an_empty_author(monkeypatch):             # item 5a
    a, b = "a" * 40, "b" * 40
    rec = _Rec(stdout=f"{a}\0\0first\0{b}\0Bob\0\0".encode())      # -z: every record ends with one NUL
    monkeypatch.setattr(gitops.docker, "run", rec)
    assert gitops.log(Paths("pass1", "control"), "x", "y") == [
        {"sha": a, "author": "", "subject": "first"}, {"sha": b, "author": "Bob", "subject": ""}]


def test_commits_between_keeps_an_empty_last_message(monkeypatch):
    a, b = "a" * 40, "b" * 40
    rec = _Rec(stdout=f"{a}\0Fix\n\0{b}\0\n\0".encode())
    monkeypatch.setattr(gitops.docker, "run", rec)
    out = gitops.commits_between(Paths("pass1", "control"), "x", "y")
    assert [r.split("\x1f", 1) for r in out.split("\x1e") if r] == [[a, "Fix"], [b, ""]]


def test_nul_fields_refuses_output_that_does_not_end_with_the_record_nul(monkeypatch):
    rec = _Rec(stdout=b"a\0b\0c")
    monkeypatch.setattr(gitops.docker, "run", rec)
    with pytest.raises(RuntimeError):
        gitops.log(Paths("pass1", "control"), "x", "y")


def test_log_output_is_forced_to_utf8_whatever_the_repo_config_says(monkeypatch):     # item 5b
    s = gitops.spec(Paths("pass1", "control"), ["log"])
    assert "i18n.logOutputEncoding=UTF-8" in s.cmd
    rec = _Rec(stdout=b"")
    monkeypatch.setattr(gitops.docker, "run", rec)
    gitops.log(Paths("pass1", "control"), "x", "y"); gitops.commits_between(Paths("pass1", "control"), "x", "y")
    assert all("--encoding=UTF-8" in _git_args(s) for s in rec.specs)


def test_restore_probes_stop_with_a_short_grace_and_the_bound_says_so(tmp_state, monkeypatch):   # item 8
    from runner import repo as r
    p = _live_tree(tmp_state)
    seen = []
    def fake_run(s, input=None, timeout=None, stop_grace=30):
        seen.append((timeout, stop_grace)); return subprocess.CompletedProcess([], 0, b"", b"")
    monkeypatch.setattr(r.docker, "run", fake_run)
    r._await_visible_in_containers(p, timeout=30)
    assert seen == [(r.PROBE_SECONDS, r.PROBE_STOP_GRACE)] and r.PROBE_STOP_GRACE <= 2
    assert "PROBE_STOP_GRACE" in r._await_visible_in_containers.__doc__


def test_docker_run_passes_the_stop_grace_on_timeout(monkeypatch):
    stops = []
    monkeypatch.setattr(gitops.docker.subprocess, "run",
                        lambda argv, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired(argv, 1))
                        if argv[:2] == ["docker", "run"] else stops.append(argv))
    s = dataclasses.replace(gitops.spec(Paths("pass1", "control"), ["status"]), mounts=[])
    with pytest.raises(subprocess.TimeoutExpired):
        gitops.docker.run(s, timeout=1, stop_grace=2)
    assert stops[0][:4] == ["docker", "stop", "-t", "2"]


import dataclasses


def test_bare_tree_mounts_the_bare_clone_read_only_and_only_the_tree_writable(tmp_state, monkeypatch):  # breakage 2
    p = Paths("dry9", "dryrun")
    bare, tree = tmp_state / "w" / "clone.git", tmp_state / "w" / "tree"
    bare.mkdir(parents=True)
    rec = _Rec(stdout=b"")
    monkeypatch.setattr(gitops.docker, "run", rec)
    gitops.bare_tree(p, bare, "main", tree)
    [s] = rec.specs
    assert sorted((str(m.host), m.ctr, m.ro) for m in s.mounts) == [(str(bare), "/in/bare.git", True),
                                                                    (str(tree), "/out", False)]
    assert s.network == "none"


def test_publish_scans_the_tree_of_the_very_clone_it_pushes(tmp_state, monkeypatch):     # breakage 2
    p = Paths("pass1", "control")
    p.scratch.mkdir(parents=True)
    calls = []
    def fake_bundle(p_, dest, refs=()):
        dest.write_bytes(b"# v2 git bundle\n"); calls.append("bundle"); return dest
    monkeypatch.setattr(gitops, "bundle", fake_bundle)
    monkeypatch.setattr(gitops, "clone_bundle_bare", lambda b, d: (d.mkdir(), calls.append(("clone", d))))
    monkeypatch.setattr(gitops, "bare_tree", lambda p_, bare, ref, dest: (dest.mkdir(), calls.append(("tree", bare))))
    monkeypatch.setattr(gitops, "push_from_bare", lambda bare, url, ref="main": calls.append(("push", bare)))
    assert repo.publish(p, "pass1", ask=lambda q: True, scan=lambda d: calls.append("scan") or [])
    assert [c if isinstance(c, str) else c[0] for c in calls] == ["bundle", "clone", "tree", "scan", "push"]
    assert calls[1][1] == calls[2][1] == calls[4][1]


# --- restore consistency (item 7 residual, breakage 3) -------------------------------------------------------

def _leftover(p, kind, **trees):
    d = p.base / f".{kind}-deadbeef0000"
    d.mkdir()
    for name, text in trees.items():
        (d / name).mkdir(); (d / name / "marker").write_text(text)
    return d


def test_gitops_refuses_to_touch_an_arm_with_an_interrupted_restore(tmp_state, monkeypatch):
    p = _live_tree(tmp_state); _leftover(p, "aside", home="old")
    monkeypatch.setattr(gitops.docker, "run", lambda *a, **k: pytest.fail("ran a container"))
    with pytest.raises(gitops.InterruptedRestore):
        gitops.head(p)


def test_recover_rolls_back_a_swap_interrupted_before_anything_moved_in(tmp_state):
    p = _live_tree(tmp_state)
    import shutil; shutil.rmtree(p.home)
    _leftover(p, "aside", home="old"); _leftover(p, "restore", work="half")     # died after home went aside
    repo.recover(p)
    assert (p.home / "marker").read_text() == "old" and (p.work / "current").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_recover_rolls_back_a_swap_interrupted_between_the_two_moves_in(tmp_state):
    p = _live_tree(tmp_state)
    import shutil; shutil.rmtree(p.work)                                          # home is the restored one
    (p.home / "current").rename(p.home / "restored")
    _leftover(p, "aside", home="old", work="old-w")
    repo.recover(p)
    assert (p.home / "marker").read_text() == "old" and (p.work / "marker").read_text() == "old-w"
    assert not (p.home / "restored").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_recover_finishes_a_swap_that_only_missed_its_cleanup(tmp_state):
    p = _live_tree(tmp_state); _leftover(p, "aside", home="old", work="old-w")
    repo.recover(p)
    assert (p.home / "current").exists() and (p.work / "current").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_recover_raises_on_an_ambiguous_state(tmp_state):
    p = _live_tree(tmp_state); _leftover(p, "aside", home="a")
    (p.base / ".aside-feedface0000").mkdir(); (p.base / ".aside-feedface0000" / "work").mkdir()
    with pytest.raises(gitops.InterruptedRestore):
        repo.recover(p)


def test_snapshot_and_restore_recover_first(tmp_state, monkeypatch):
    from runner import repo as r
    p = _live_tree(tmp_state); _leftover(p, "restore", work="half")
    monkeypatch.setattr(r, "_run", lambda s, what: None)
    r.snapshot(p, 9)
    assert not list(p.base.glob(".restore-*"))


def test_a_restore_that_cannot_create_its_dirs_leaves_nothing_behind(tmp_state, monkeypatch):
    p = _live_tree(tmp_state); _fake_restore(monkeypatch)
    real = Path.mkdir
    def failing(self, *a, **k):
        if self.name.startswith(".aside-"):
            raise OSError("no space")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "mkdir", failing)
    with pytest.raises(OSError):
        repo.restore(p, 1)
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]


def test_a_failed_rollback_keeps_the_aside_and_reports_both_errors(tmp_state, monkeypatch):
    p = _live_tree(tmp_state); _fake_restore(monkeypatch)
    real = Path.rename
    def flaky(self, target):
        if self.name == "work" and self.parent.name.startswith(".restore-"):
            raise OSError("disk full")                                  # the second move-in fails
        if self.parent.name.startswith(".aside-"):
            raise OSError("rollback blocked")                           # ...and so does putting things back
        return real(self, target)
    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(OSError, match="disk full") as ei:
        repo.restore(p, 1)
    assert any("rollback blocked" in n for n in getattr(ei.value, "__notes__", []))
    [aside] = p.base.glob(".aside-*")
    assert (aside / "home" / "current").exists()                        # the only copy of the old home survives
    monkeypatch.setattr(Path, "rename", real)
    repo.recover(p)
    assert (p.home / "current").exists() and (p.work / "current").exists()
    assert sorted(x.name for x in p.base.iterdir()) == ["home", "snapshots", "work"]
