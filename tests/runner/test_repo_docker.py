"""Real git, in real containers (review S-1). Run with `--run-docker`.

The hostile-repo tests plant every git execution vector an arm could leave in its repo and then drive every
gitops operation. Each planted command tries to write a marker into a HOST directory that is never mounted
into any container: if any of them ran on the host, that directory would stop being empty. Each also writes a
second marker into the arm's own home (mounted read-write only for write operations), which proves the vector
was live and fired *inside* the container, so the empty host directory is not a vacuous pass (preflight M2).
"""
import subprocess
import tarfile
import pytest
from runner import docker, gitops, repo
from runner.paths import Paths

pytestmark = pytest.mark.docker


@pytest.fixture(autouse=True)
def _no_leftover_containers():
    yield
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "label=bakeoff.run=dry9/dryrun"],
                          capture_output=True, text=True).stdout.split()
    docker.sweep("bakeoff.run=dry9/dryrun")
    assert left == [], "a git container outlived its operation"


@pytest.fixture
def P(tmp_state):
    p = Paths("dry9", "dryrun")
    repo.init(p, "dryrun", "dry9")
    return p


def _out(r) -> str:
    return r.stdout.decode().strip()


def test_new_repo_has_one_empty_commit_on_main_with_the_neutral_identity(P):
    assert gitops.git(P, "rev-list", "--count", "HEAD").stdout.strip() == b"1"
    assert gitops.ls_files(P, "HEAD") == []
    s = gitops.state(P)
    assert s.branch == "main" and s.main == s.head and not s.dirty and s.head_in_main
    assert gitops.log(P, "HEAD~0", "HEAD") == [] and "Developer <developer@troupe.run>" in gitops.show(P, "HEAD")


def test_new_repo_has_a_local_bare_origin_with_main_pushed_upstream(P):      # preflight B4 (owner answer)
    assert _out(gitops.git(P, "remote", "get-url", "origin")) == gitops.ORIGIN == "/home/actor/origin.git"
    assert _out(gitops.git(P, "rev-parse", "--abbrev-ref", "main@{upstream}")) == "origin/main"
    assert (P.home / "origin.git" / "HEAD").is_file()                  # inside the arm's own mounts
    remote_main = _out(gitops.git(P, "ls-remote", "origin", "refs/heads/main", write=True)).split("\t")[0]
    assert remote_main == gitops.main_sha(P)
    assert _out(gitops.git(P, "remote")) == "origin"                   # no other remote, no network URL
    (P.repo / "a.py").write_text("1")
    sha = gitops.commit_all(P, gitops.IDENTITY, "a")
    gitops.git(P, "push", "-q", "origin", "main", write=True)          # `git push origin main` works
    assert _out(gitops.git(P, "ls-remote", "origin", "refs/heads/main", write=True)).split("\t")[0] == sha


def test_origin_is_restored_with_the_step(P):
    repo.snapshot(P, 1)
    (P.repo / "a.py").write_text("1")
    gitops.commit_all(P, gitops.IDENTITY, "a")
    gitops.git(P, "push", "-q", "origin", "main", write=True)
    repo.restore(P, 1)
    assert _out(gitops.git(P, "ls-remote", "origin", "refs/heads/main", write=True)).split("\t")[0] == gitops.main_sha(P)


def test_restore_returns_home_and_work_exactly_to_the_snapshot(P):
    repo.snapshot(P, 3)
    (P.repo / "junk.py").write_text("x"); (P.config_dir / "leak").write_text("y")
    repo.restore(P, 3)
    assert not (P.repo / "junk.py").exists() and not (P.config_dir / "leak").exists()


def test_export_contains_only_committed_files_of_main(P):
    (P.repo / "a.py").write_text("1")
    gitops.commit_all(P, gitops.IDENTITY, "a")
    (P.repo / "untracked.py").write_text("2")
    repo.export(P, gitops.main_sha(P), P.scratch / "x")
    assert sorted(f.name for f in (P.scratch / "x").iterdir()) == ["a.py"]


def test_work_on_a_branch_is_not_in_main(P):                                  # review F-1
    gitops.git(P, "checkout", "-q", "-b", "feature", write=True)
    (P.repo / "b.py").write_text("1")
    gitops.commit_all(P, gitops.IDENTITY, "b")
    s = gitops.state(P)
    assert s.branch == "feature" and not s.head_in_main and s.main != s.head


def test_reads_report_what_the_tree_holds(P):
    base = gitops.head(P)
    (P.repo / "a.py").write_text("one\ntwo\n"); (P.repo / "notes.md").write_text("needle\n")
    sha = gitops.commit_all(P, gitops.TEAMMATE, "add a\n\nbody line")
    assert gitops.numstat(P, base, sha) == [(2, 0, "a.py"), (1, 0, "notes.md")]
    assert "2 files changed" in gitops.diffstat(P, base, sha)
    assert gitops.grep_files(P, sha, "needle") == ["notes.md"]
    assert gitops.log(P, base, sha) == [{"sha": sha, "author": "Sam Teammate", "subject": "add a"}]
    [rec] = [r for r in gitops.commits_between(P, base, sha).split("\x1e") if r.strip()]
    assert rec.strip().split("\x1f") == [sha, "add a\nbody line"]
    (P.repo / "a.py").write_text("changed\n"); (P.repo / "new.py").write_text("n")
    assert "a.py" in gitops.worktree_diffstat(P)
    assert gitops.porcelain(P).splitlines() == [" M a.py", "?? new.py"]
    gitops.checkout_paths(P, ["a.py"]); gitops.remove_untracked(P, ["new.py"])
    assert gitops.porcelain(P) == "" and not gitops.state(P).dirty


def test_a_hostile_hook_and_fsmonitor_never_run_on_the_host(P, tmp_path_factory):     # review S-1, M2
    marker = tmp_path_factory.mktemp("host-markers") / "pwned"
    hook = P.repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker} 2>/dev/null; touch /home/actor/hook-ran; exit 0\n")
    hook.chmod(0o755)
    gitops.git(P, "config", "core.fsmonitor", f"touch {marker}; false", write=True)
    gitops.state(P); gitops.porcelain(P)
    (P.repo / "c.py").write_text("1"); gitops.commit_all(P, gitops.IDENTITY, "c")
    assert not marker.exists()                        # the host path does not exist inside the container
    assert (P.home / "hook-ran").exists()             # ...and the hook really ran, in the container


def test_restore_refuses_a_symlink_that_points_outside(P, tmp_path):          # review S-1 extension
    (P.repo / "evil").symlink_to("/etc/passwd")
    repo.snapshot(P, 4)
    with pytest.raises(tarfile.AbsoluteLinkError):
        repo.restore(P, 4)
    assert (P.repo / ".git").exists()                   # a refused restore leaves the current state intact


# --- hostile-repo matrix ----------------------------------------------------------------------------------

HOOKS = ["pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "post-checkout", "pre-push",
         "reference-transaction", "post-index-change", "pre-auto-gc", "post-rewrite"]


def _payload(host_dir, name: str, tail: str = "true") -> str:
    """Shell text that tries the host marker, leaves the in-container proof, then runs `tail` (so git sees
    a well-behaved command and carries on: `cat` for filters/textconv, `true` or `false` elsewhere)."""
    return f"touch {host_dir}/{name} 2>/dev/null; touch /home/actor/ran/{name} 2>/dev/null; {tail}"


def _plant(p: Paths, host_dir, scenario: str) -> None:
    """Write the vectors straight into `.git` from the host — writing files executes nothing; this is exactly
    what an arm with read-write access to its repo can do."""
    g = p.repo / ".git"
    (p.home / "ran").mkdir()
    hooks_dir = g / "hooks" if scenario == "dotgit-hooks" else g / "evil-hooks"
    hooks_dir.mkdir(exist_ok=True)
    for h in HOOKS:
        f = hooks_dir / h
        f.write_text(f"#!/bin/sh\n{_payload(host_dir, 'hook-' + h, 'exit 0')}\n")
        f.chmod(0o755)
    (g / "info").mkdir(exist_ok=True)
    (g / "info" / "attributes").write_text("* diff=evil filter=evil\n")
    q = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    vectors = {
        ("core", "fsmonitor"): _payload(host_dir, "fsmonitor", "false"),
        ("core", "sshCommand"): _payload(host_dir, "sshCommand"),
        ("core", "askPass"): _payload(host_dir, "askPass"),
        ("core", "editor"): _payload(host_dir, "editor"),
        ("core", "pager"): _payload(host_dir, "pager", "cat"),
        ("sequence", "editor"): _payload(host_dir, "sequence-editor"),
        ("credential", "helper"): "!" + _payload(host_dir, "credential-helper"),
        ("diff", "external"): _payload(host_dir, "diff-external"),
        ('diff "evil"', "textconv"): _payload(host_dir, "textconv", "cat"),
        ('filter "evil"', "clean"): _payload(host_dir, "filter-clean", "cat"),
        ('filter "evil"', "smudge"): _payload(host_dir, "filter-smudge", "cat"),
        ("gpg", "program"): _payload(host_dir, "gpg-program", "false"),
        ("commit", "gpgsign"): "true",
        ("uploadpack", "packObjectsHook"): _payload(host_dir, "packObjectsHook", "false"),
        ('remote "evil"', "url"): "ssh://evil.invalid/x.git",
        ('remote "evil"', "uploadpack"): _payload(host_dir, "remote-uploadpack"),
    }
    text = ""
    if scenario == "hooks-path-and-includes":
        # include.path / includeIf: the included files carry the vectors (they come first, so a later direct
        # key in .git/config would override them — this scenario has none, the includes are the live values)
        (g / "evil.inc").write_text("".join(f'[{s}]\n\t{k} = "{q(v)}"\n' for (s, k), v in vectors.items()
                                            if s.startswith(("core", "diff", "credential"))))
        (g / "evil-if.inc").write_text("".join(f'[{s}]\n\t{k} = "{q(v)}"\n' for (s, k), v in vectors.items()
                                               if not s.startswith(("core", "diff", "credential"))))
        text += f'[include]\n\tpath = evil.inc\n[includeIf "gitdir:/"]\n\tpath = evil-if.inc\n'
        text += f"[core]\n\thooksPath = {p.container_repo}/.git/evil-hooks\n"
    else:
        text += "".join(f'[{s}]\n\t{k} = "{q(v)}"\n' for (s, k), v in vectors.items())
    with (g / "config").open("a") as f:
        f.write(text)


@pytest.mark.parametrize("scenario", ["dotgit-hooks", "hooks-path-and-includes"])
def test_no_planted_git_vector_ever_executes_on_the_host(P, tmp_path_factory, scenario, monkeypatch):
    host = tmp_path_factory.mktemp(f"host-markers-{scenario}")
    base = gitops.head(P)
    (P.repo / ".gitattributes").write_text("* diff=evil filter=evil\n")   # committed: reaches publish's clone too
    (P.repo / "a.py").write_text("one\n")
    gitops.commit_all(P, gitops.IDENTITY, "attributes")
    _plant(P, host, scenario)

    # every read
    gitops.state(P); gitops.porcelain(P); gitops.head(P); gitops.main_sha(P)
    (P.repo / "a.py").write_text("two\n"); (P.repo / "u.py").write_text("u\n")
    gitops.worktree_diffstat(P); gitops.porcelain(P); gitops.state(P)
    # every write
    sha = gitops.commit_all(P, gitops.IDENTITY, "change")                 # hooks fire, in the container
    gitops.git(P, "checkout", "-q", "-b", "side", write=True)
    gitops.git(P, "checkout", "-q", "main", write=True)
    gitops.git(P, "push", "-q", "origin", "main", write=True)
    (P.repo / "a.py").write_text("three\n"); (P.repo / "v.py").write_text("v\n")
    gitops.checkout_paths(P, ["a.py"]); gitops.remove_untracked(P, ["v.py"])
    # more reads over history
    gitops.diffstat(P, base, sha); gitops.numstat(P, base, sha); gitops.show(P, sha)
    gitops.log(P, base, sha); gitops.commits_between(P, base, sha); gitops.ls_files(P, sha)
    gitops.grep_files(P, sha, "two"); gitops.archive(P, sha)
    repo.export(P, sha, P.scratch / "export")
    gitops.bundle(P, P.scratch / "b" / "all.bundle")
    repo.snapshot(P, 5); repo.restore(P, 5)
    # publish: bundle in a container -> host bare clone -> secret scan -> host push (to a local bare target)
    target = tmp_path_factory.mktemp("publish-target") / "t.git"
    subprocess.run(["git", "init", "-q", "--bare", str(target)], check=True,
                   env={**gitops._host_env()})
    monkeypatch.setattr(repo, "github_slug", lambda pass_, arm: "troupe-run/test")
    real_push = gitops.push_from_bare
    monkeypatch.setattr(gitops, "push_from_bare", lambda bare, url, ref="main": real_push(bare, str(target), ref))
    scanned = []
    assert repo.publish(P, "dry9", ask=lambda q: True, scan=lambda d: scanned.append(d) or [])
    assert scanned and sorted(f.name for f in scanned[0].iterdir()) == [".gitattributes", "a.py", "u.py"]
    [clone] = (P.scratch / "publish").glob("*/clone.git")
    bare_cfg = (clone / "config").read_text()
    for key in ("fsmonitor", "hooksPath", "credential", "sshCommand", "external", "textconv", "filter",
                "include", "gpg", "evil", "pager", "editor", "askPass", "uploadpack"):
        assert key not in bare_cfg, key                                   # a bundle carries no config
    assert not [h for h in (clone / "hooks").iterdir()
                if not h.name.endswith(".sample")]                       # ...and no hooks
    pushed = subprocess.run(["git", "-C", str(target), "rev-parse", "main"], capture_output=True, text=True,
                            env=gitops._host_env()).stdout.strip()
    assert pushed == gitops.main_sha(P)

    assert sorted(x.name for x in host.iterdir()) == []                  # nothing ran on the host
    fired = sorted(x.name for x in (P.home / "ran").iterdir())
    print(f"\n[{scenario}] fired in the container: {fired}")
    # the vectors were live: git executed them — inside the container
    assert {"hook-pre-commit", "hook-commit-msg", "hook-post-commit", "hook-post-checkout",
            "hook-reference-transaction", "hook-pre-push", "fsmonitor", "filter-clean"} <= set(fired), fired
