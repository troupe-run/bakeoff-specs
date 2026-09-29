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


HOST_HELPERS = {"ls_remote_tag", "commit_harness_file", "harness_is_clean", "clone_bundle_bare",
                "archive_from_bare", "push_from_bare"}


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
