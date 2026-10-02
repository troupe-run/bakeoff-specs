"""Real git, in real containers (review S-1). Run with `--run-docker`.

The hostile-repo tests plant every git execution vector an arm could leave in its repo and then drive every
gitops operation. Each planted command tries to write a marker into a HOST directory that is never mounted
into any container: if any of them ran on the host, that directory would stop being empty. Each also writes a
second marker into the arm's own home (mounted read-write only for write operations), which proves the vector
was live and fired *inside* the container, so the empty host directory is not a vacuous pass (preflight M2).
"""
import os
import subprocess
import pytest
from runner import docker, gitops, repo, transcripts
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
    assert [f.name for f in transcripts.safe_files(P.scratch / "x", "*")] == ["a.py"]


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


def test_log_is_exact_for_an_empty_message_an_empty_author_and_a_utf16_log_encoding(P):   # fix round 2, item 5
    root = gitops.main_sha(P)
    gitops.git(P, "commit", "-q", "--allow-empty", "--allow-empty-message", "-m", "", write=True,
               env={"GIT_AUTHOR_NAME": "Dev", "GIT_AUTHOR_EMAIL": "d@x", "GIT_COMMITTER_NAME": "Dev",
                    "GIT_COMMITTER_EMAIL": "d@x"})
    empty_msg = gitops.head(P)
    tree = _out(gitops.git(P, "rev-parse", "HEAD^{tree}"))
    raw = (f"tree {tree}\nparent {empty_msg}\nauthor  <a@x> 1700000000 +0000\n"
           f"committer  <a@x> 1700000000 +0000\n\nno author\n").encode()
    crafted = _out(gitops.git(P, "hash-object", "-t", "commit", "-w", "--literally", "--stdin", input=raw, write=True))
    gitops.git(P, "update-ref", "refs/heads/main", crafted, write=True)
    with (P.repo / ".git" / "config").open("a") as f:
        # Arm-writable. Probed 2026-09-29: git 2.39.5 in these images does NOT actually re-encode -z output to
        # UTF-16LE (with or without our override), so this guards a future git/image, it does not demonstrate
        # corruption today; the pure test checks the override is always passed.
        f.write("[i18n]\n\tlogOutputEncoding = UTF-16LE\n")
    assert gitops.log(P, root, "main") == [
        {"sha": crafted, "author": "", "subject": "no author"},
        {"sha": empty_msg, "author": "Dev", "subject": ""}]
    recs = [r.split("\x1f", 1) for r in gitops.commits_between(P, root, "main").split("\x1e") if r]
    assert recs == [[crafted, "no author"], [empty_msg, ""]]
    assert gitops.log(P, empty_msg, empty_msg) == [] and gitops.commits_between(P, empty_msg, empty_msg) == ""


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


def test_snapshot_restore_round_trips_absolute_and_escaping_links_as_plain_links(P, tmp_path_factory):
    """fix round 1: a venv's absolute `bin/python` link must survive a restore (filter="data" refused it), and
    no link is ever followed: nothing is written outside the arm's trees."""
    outside = tmp_path_factory.mktemp("outside")
    depth = len(P.repo.relative_to(outside.parent).parts)
    escape = "/".join([".."] * depth) + f"/{outside.name}/owned"
    links = {".venv/bin/python": "/usr/local/bin/python3.12", "abs": "/etc/passwd", "esc": escape,
             "dir-out": str(outside)}
    (P.repo / ".venv" / "bin").mkdir(parents=True)
    for name, target in links.items():
        (P.repo / name).symlink_to(target)
    (P.home / "home-esc").symlink_to(escape)
    repo.snapshot(P, 4)
    for name in links:
        (P.repo / name).unlink()
    (P.repo / "later.py").write_text("x")
    repo.restore(P, 4)
    for name, target in links.items():
        assert (P.repo / name).is_symlink() and os.readlink(P.repo / name) == target, name
    assert os.readlink(P.home / "home-esc") == escape and not (P.repo / "later.py").exists()
    assert list(outside.iterdir()) == []                  # nothing written through any link
    assert sorted(x.name for x in P.base.iterdir()) == ["home", "scratch", "snapshots", "work"]
    assert gitops.main_sha(P)                             # containers see the restored repo straight away


def test_export_writes_committed_links_as_links_and_follows_none(P, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside-export")
    (P.repo / "abs").symlink_to(str(outside)); (P.repo / "real.py").write_text("1")
    sha = gitops.commit_all(P, gitops.IDENTITY, "links")
    repo.export(P, sha, P.scratch / "x")
    assert os.readlink(P.scratch / "x" / "abs") == str(outside) and list(outside.iterdir()) == []
    assert [f.name for f in transcripts.safe_files(P.scratch / "x", "*")] == ["real.py"]   # host reads never follow


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
    first = gitops.commit_all(P, gitops.IDENTITY, "attributes")          # a.py "one"
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
    # A checkout that MUST smudge (final fix batch, Task 8): an older blob of a.py into index and worktree, then
    # back. Both replace the index entry with a different blob, so git writes the file whatever the worktree's
    # stat looks like from inside the container; the host write above may not be visible there yet (Docker
    # Desktop), which made `checkout_paths` alone a nondeterministic positive control for filter-smudge.
    gitops.git(P, "checkout", "-q", first, "--", "a.py", write=True)
    gitops.git(P, "checkout", "-q", sha, "--", "a.py", write=True)
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
    assert repo.publish(P, "dry9", ask=lambda q: True, scan=lambda d, h: scanned.append(d) or [])
    assert scanned and [f.name for f in transcripts.safe_files(scanned[0], "*")] == [".gitattributes", "a.py", "u.py"]
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
    assert set(fired) == FIRE_IN_CONTAINER, fired
    # These never fire ANYWHERE under gitops — not because a container contains them, but because nothing
    # triggers them (reads pass --no-textconv/--no-ext-diff and disable the pager; writes never sign or open an
    # editor; the only push goes to the local origin, so no credential helper, ssh or askpass). Their absence
    # here is NOT evidence of containment; the negative control shows textconv and diff.external do fire under
    # host git.
    assert not NEVER_FIRE & set(fired)


FIRE_IN_CONTAINER = {"filter-clean", "filter-smudge", "fsmonitor", "hook-commit-msg", "hook-post-checkout",
                     "hook-post-commit", "hook-post-index-change", "hook-pre-commit", "hook-pre-push",
                     "hook-prepare-commit-msg", "hook-reference-transaction"}
NEVER_FIRE = {"textconv", "diff-external", "credential-helper", "sshCommand", "askPass", "pager", "editor",
              "sequence-editor", "gpg-program", "packObjectsHook", "remote-uploadpack", "hook-pre-auto-gc",
              "hook-post-rewrite"}


@pytest.mark.host_exec
@pytest.mark.parametrize("scenario", ["dotgit-hooks", "hooks-path-and-includes"])
def test_negative_control_host_git_on_the_planted_repo_does_run_the_vectors_on_the_host(P, tmp_path_factory,
                                                                                         scenario):
    """Opt-in (`--run-host-exec`): executes the planted payloads ON THE HOST (each only touches a file in a
    pytest tmp dir). Proves the hostile matrix discriminates: the same repo under host git — what the runner
    did before S-1 — writes host markers, where gitops writes none."""
    host = tmp_path_factory.mktemp(f"negctl-{scenario}")
    (P.repo / ".gitattributes").write_text("* diff=evil filter=evil\n"); (P.repo / "a.py").write_text("one\n")
    gitops.commit_all(P, gitops.IDENTITY, "attributes")
    _plant(P, host, scenario)
    if scenario == "hooks-path-and-includes":               # hooksPath names the container path; use the host one
        cfg = P.repo / ".git" / "config"
        cfg.write_text(cfg.read_text().replace(P.container_repo, str(P.repo)))
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
    g = lambda *a: subprocess.run(["git", "-C", str(P.repo), *a], env=env, capture_output=True)
    (P.repo / "a.py").write_text("two\n")
    g("status"); g("diff"); g("log", "-p", "-1"); g("add", "-A")
    g("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-m", "x"); g("show", "HEAD")
    on_host = {x.name for x in host.iterdir()}
    assert {"textconv", "diff-external", "fsmonitor", "filter-clean", "hook-pre-commit"} <= on_host, on_host


# ---- restore onto a Docker Desktop bind mount (2026-10-02) ------------------------------------------------------
# A uv cache in an arm's home holds `bin/` dirs of symlinks to absolute paths that exist only in the arm container.
# GNU tar extracts such links via placeholders, and on Docker Desktop's file sharing that failed every restore with
# "Directory renamed before its status could be extracted" (live pass1, ccsdd step 2).

def _plant_uv_cache_like_home(P, packages: int = 24, files: int = 60, venvs: int = 3) -> None:
    """The shape of a real uv cache in an arm home (synthetic names and content): unpacked wheels under archive-v0,
    `wheels-v6` and `environments-v2` links into them via `..`, and venvs whose `bin/python` is a link to an absolute
    interpreter path that exists only in the arm container, with site-packages hardlinked to the unpacked wheels.
    Plus odd permission bits and fixed mtimes, so the exactness comparison has something to catch."""
    import os
    uv = P.home / ".cache" / "uv"
    arch = uv / "archive-v0"
    for k in range(packages):
        pkg = arch / f"pkg{k:02d}id" / f"pkg{k:02d}"
        pkg.mkdir(parents=True)
        for f in range(files):
            (pkg / f"m{f:03d}.py").write_text(f"# {k} {f}\n" * 20)
        (uv / "wheels-v6" / "pypi" / f"pkg{k:02d}").mkdir(parents=True)
        os.symlink(f"../../../archive-v0/pkg{k:02d}id", uv / "wheels-v6" / "pypi" / f"pkg{k:02d}" / "1.0-py3-none-any")
    (uv / "environments-v2" / "envhash").mkdir(parents=True)
    for v in range(venvs):
        venv = arch / f"venv{v}id"
        (venv / "bin").mkdir(parents=True)
        os.symlink("/opt/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12", venv / "bin" / "python")  # dangling
        os.symlink("python", venv / "bin" / "python3")
        (venv / "bin" / "pytest").write_text("#!/bin/sh\n"); os.chmod(venv / "bin" / "pytest", 0o755)
        os.symlink("lib", venv / "lib64")
        site = venv / "lib" / "python3.12" / "site-packages"
        for k in range(packages):
            (site / f"pkg{k:02d}").mkdir(parents=True)
            for f in range(files):
                os.link(arch / f"pkg{k:02d}id" / f"pkg{k:02d}" / f"m{f:03d}.py", site / f"pkg{k:02d}" / f"m{f:03d}.py")
        os.symlink(f"../../archive-v0/venv{v}id", uv / "environments-v2" / "envhash" / f"env{v}")
    (P.home / "group-writable.txt").write_text("g"); os.chmod(P.home / "group-writable.txt", 0o664)
    (P.home / "private").mkdir(); os.chmod(P.home / "private", 0o700)
    (P.home / "readonly.txt").write_text("r"); os.chmod(P.home / "readonly.txt", 0o444)
    os.utime(arch / "pkg00id" / "pkg00" / "m000.py", (1_700_000_000, 1_700_000_000))
    os.utime(arch / "pkg00id" / "pkg00", (1_700_000_100, 1_700_000_100))


def _members(tar_path) -> dict:
    """Every member of a snapshot by name: type, permission bits, size, mtime, link target and content digest.
    The two root dirs' mtimes are left out (restore's visibility probe creates and deletes a token in each)."""
    import hashlib, tarfile
    out = {}
    with tarfile.open(tar_path) as t:
        for m in t:
            digest = hashlib.sha256(t.extractfile(m).read()).hexdigest() if m.isfile() else None
            out[m.name.rstrip("/")] = (m.type, m.mode & 0o7777, m.size, None if m.name.rstrip("/") in ("home", "work")
                                       else m.mtime, m.linkname, digest)
    return out


def test_restore_of_a_home_with_absolute_symlinks_onto_a_bind_mount_succeeds_and_matches_the_snapshot(P):
    _plant_uv_cache_like_home(P)
    snap = repo.snapshot(P, 2)
    (P.repo / "junk.py").write_text("x"); (P.home / ".cache" / "uv" / "new").write_text("n")
    repo.restore(P, 2)
    again = repo.snapshot(P, "after-restore")      # retries tar's "file changed as we read it"
    before, after = _members(snap), _members(again)
    assert before["home/.cache/uv/archive-v0/venv0id/bin/python"][4] == \
        "/opt/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12"
    assert any(n.startswith("home/origin.git/objects/") for n in before)        # a real git repo is in it
    assert after == before


def test_extract_snapshot_of_a_home_with_absolute_symlinks_onto_a_bind_mount_succeeds(P):
    import os
    _plant_uv_cache_like_home(P)
    snap = repo.snapshot(P, 2)
    dest = repo.extract_snapshot(P, snap, P.scratch / "scan")
    link = dest / "home/.cache/uv/archive-v0/venv2id/bin/python"
    assert os.readlink(link) == "/opt/python/cpython-3.12-linux-aarch64-gnu/bin/python3.12"
    repo.remove_tree(dest)


@pytest.mark.parametrize("bad", ["home/../escape", "/etc/x", "etc/x", "./home/x", "homework/x"])
def test_restore_refuses_a_snapshot_with_a_member_name_outside_home_and_work_or_with_dotdot(P, bad):
    import io, tarfile
    with tarfile.open(P.snapshots / "step-09.tar", "w") as t:
        t.add(P.home, arcname="home", recursive=False)
        t.add(P.work, arcname="work", recursive=False)
        info = tarfile.TarInfo(bad); info.size = 1
        t.addfile(info, io.BytesIO(b"x"))
    assert bad in tarfile.open(P.snapshots / "step-09.tar").getnames()     # the name is stored as written
    (P.repo / "keep.py").write_text("k")
    with pytest.raises(docker.ContainerError, match="outside home/ and work/ or with a '..' component"):
        repo.restore(P, 9)
    assert (P.repo / "keep.py").read_text() == "k"          # a refused extract leaves the live trees untouched
