"""Arm repo lifecycle: init, snapshots, restore, export, bundle, GitHub plan/verify, publish.

Every git command on an arm repo goes through `gitops` (containers; review S-1). The host never creates or
extracts a tar of an arm tree either: snapshot, restore and export run `tar` inside a network-less, read-only-
root container of the arm's image, so links (absolute, `..`-escaping, a venv's `bin/python`) are just data and
any extraction trick is contained. The host only renames whole directories, deletes them without following
links, and calls `gh` for the owner-facing GitHub plan and verification.
"""
from __future__ import annotations
import dataclasses, json, os, shutil, stat, subprocess, time, uuid
from pathlib import Path
from runner import config, docker, gitops
from runner.config import GITHUB_ORG as ORG, github_slug     # single source; re-exported (Task 5 / M4)
from runner.docker import Mount, RunSpec
from runner.paths import Paths

__all__ = ["ORG", "github_slug", "ensure_private_repo", "init", "head", "snapshot", "restore", "recover", "export", "bundle", "github_plan",
           "github_verify", "verify_ok", "publish", "pat_instructions", "extract_snapshot", "remove_tree"]


def init(p: Paths, arm: str, pass_: str) -> str:
    """A pass starts from nothing (OD20): fresh home and repo, `main` pushed to the local bare origin (B4)."""
    if (arm, pass_) != (p.arm, p.pass_):
        raise ValueError(f"init({arm!r}, {pass_!r}) does not match {p}")
    if p.base.exists():
        raise FileExistsError(f"{p.base} exists; a pass starts from nothing (OD20)")
    for d in (p.config_dir, p.repo, p.snapshots, p.scratch):
        d.mkdir(parents=True)
    name, email = gitops.IDENTITY
    (p.home / ".gitconfig").write_text(f"[user]\n\tname = {name}\n\temail = {email}\n"
                                       f"[init]\n\tdefaultBranch = main\n[safe]\n\tdirectory = *\n")
    return gitops.init_repo(p)


def head(p: Paths) -> str:
    return gitops.head(p)


def _snap_name(step: int | str) -> str:
    return f"step-{step:02d}.tar" if isinstance(step, int) else f"step-{step}.tar"


def _tar_spec(p: Paths, mounts: list[Mount], script: str, *args: str, tag: str) -> RunSpec:
    """Same sandbox as a gitops read (arm image, --network none, read-only root, caps dropped), other mounts."""
    base = gitops.spec(p, [])
    return dataclasses.replace(base, name=base.name.replace("bk-git-", f"bk-{tag}-", 1), mounts=mounts,
                               workdir="/", cmd=["bash", "-c", script, tag, *args])


def _run(s: RunSpec, what: str) -> None:
    r = docker.run(s, timeout=1800)
    if r.returncode != 0:
        raise docker.ContainerError(f"{what} failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")


_SNAPSHOT_SH = r"""set -euo pipefail
tar -c -f "/snap/$1.partial" -C /src home work
mv -f "/snap/$1.partial" "/snap/$1"
"""


def snapshot(p: Paths, step: int | str) -> Path:
    """Tar of the arm-controlled trees (home — including the bare origin — and work), made in a container
    with both mounted read-only. GNU tar stores links as links and never follows them."""
    recover(p)
    p.snapshots.mkdir(parents=True, exist_ok=True)
    name = _snap_name(step)
    _run(_tar_spec(p, [Mount(p.home, "/src/home", True), Mount(p.work, "/src/work", True),
                       Mount(p.snapshots, "/snap", False)], _SNAPSHOT_SH, name, tag="snap"), f"snapshot {name}")
    return p.snapshots / name


# Extraction flags for a snapshot onto a bind mount (2026-10-02, live pass1 ccsdd step 2). Without -P, GNU tar
# extracts every symlink whose target is absolute or holds `..` as a placeholder file, swaps the real link in only
# after the whole archive, and defers the metadata of each directory holding a placeholder until then; it then
# re-stats that directory and gives up if its device/inode no longer match. On Docker Desktop's file sharing a
# directory's inode number does not stay stable over that long a gap, so a home with a uv cache (venv `bin/python`
# -> /opt/python/..., `..` links between cache dirs) failed every restore: "Directory renamed before its status
# could be extracted". -P (--absolute-names) creates links directly, so no directory's metadata waits for the end.
# What -P gives up (stripping a leading `/` and refusing `..` in member names, the placeholder guard against a
# member written through an earlier link) is replaced by `_MEMBERS_OK_SH` and by the sandbox: snapshots are made
# by `_SNAPSHOT_SH` (relative names under home/ and work/; tar -c never stores a member below a link), and the
# container can write only /out (the staging dir) and its own /tmp. -p keeps the snapshot's permission bits
# instead of masking them with the container's umask (exact restore).
_MEMBERS_OK_SH = r"""tar -t -f "/snap/$1" > /tmp/members
if grep -qvE '^(home|work)(/|$)' /tmp/members || grep -qE '(^|/)\.\.(/|$)' /tmp/members; then
  echo "snapshot $1 has a member outside home/ and work/ or with a '..' component" >&2; exit 3
fi
"""

_RESTORE_SH = r"""set -euo pipefail
""" + _MEMBERS_OK_SH + r"""tar -x -f "/snap/$1" -C /out --no-same-owner -P -p
test -d /out/home -a ! -L /out/home -a -d /out/work -a ! -L /out/work"""


def _rmtree(path: Path) -> None:
    """Delete an arm tree without following links (shutil.rmtree unlinks symlinks, never descends them);
    make read-only directories writable first so an arm's `chmod -w` cannot wedge the harness."""
    def fix(func, p_, exc):
        os.chmod(os.path.dirname(p_), stat.S_IRWXU)          # parents are real dirs: rmtree never descends links
        if func is not os.unlink and os.path.isdir(p_) and not os.path.islink(p_):
            os.chmod(p_, stat.S_IRWXU); shutil.rmtree(p_, onexc=fix)
        else:
            func(p_)
    if os.path.lexists(path):
        shutil.rmtree(path, onexc=fix)


_EXTRACT_SH = r"""set -euo pipefail
""" + _MEMBERS_OK_SH + r"""tar -x -f "/snap/$1" -C /out --no-same-owner --no-same-permissions -P
chmod -R u+rwX /out"""                  # -P: see `_RESTORE_SH` (the same Docker Desktop failure hit this scan)


def extract_snapshot(p: Paths, snapshot: Path, dest: Path) -> Path:
    """A snapshot's trees, extracted INSIDE a container into the new directory `dest` for the secret scan
    (runner.secrets.scan_snapshot) — never a restore. Made owner-readable in the container (`chmod -R`, which
    never follows links), so an arm's `chmod 000` cannot hide content from the host scanner."""
    if snapshot.parent != p.snapshots or not snapshot.is_file() or snapshot.is_symlink():
        raise FileNotFoundError(f"no snapshot {snapshot} in {p.snapshots}")
    dest.mkdir(parents=True)
    _run(_tar_spec(p, [Mount(p.snapshots, "/snap", True), Mount(dest, "/out", False)], _EXTRACT_SH,
                   snapshot.name, tag="scanx"), f"extract {snapshot.name}")
    return dest


def remove_tree(path: Path) -> None:
    """Delete an extracted arm tree without following links (see `_rmtree`)."""
    _rmtree(path)


def restore(p: Paths, step: int | str) -> None:
    """Extract the snapshot INSIDE a container into a fresh staging dir; then swap by rename-aside (current
    trees moved aside, restored trees moved in, aside deleted last). A failed extract leaves the current trees
    untouched; a failure mid-swap puts them back. If putting them back fails too, both errors are reported,
    the aside (the only copy of the previous trees) is kept, and every gitops call refuses the arm until
    `recover(p)` finishes the rollback."""
    recover(p)
    src = p.snapshots / _snap_name(step)
    if not src.is_file() or src.is_symlink():
        raise FileNotFoundError(f"no snapshot {src}")
    run_id = uuid.uuid4().hex[:12]
    staging, aside = p.base / f".restore-{run_id}", p.base / f".aside-{run_id}"
    keep_aside = False
    try:
        staging.mkdir(); aside.mkdir()
        _run(_tar_spec(p, [Mount(p.snapshots, "/snap", True), Mount(staging, "/out", False)],
                       _RESTORE_SH, src.name, tag="restore"), f"restore {src.name}")
        moved: list[tuple[Path, Path]] = []
        try:
            for live, name in ((p.home, "home"), (p.work, "work")):
                if os.path.lexists(live):
                    live.rename(aside / name); moved.append((aside / name, live))
            (staging / "home").rename(p.home)
            (staging / "work").rename(p.work)
        except BaseException as e:
            try:
                for held, live in reversed(moved):          # undo: put the previous trees back
                    if os.path.lexists(live):
                        live.rename(staging / f"failed-{live.name}")
                    held.rename(live)
            except BaseException as undo:
                keep_aside = True
                e.add_note(f"rollback failed too: {undo!r}; the previous trees are in {aside}; "
                           f"repo.recover(p) finishes the rollback")
            raise
    finally:
        _rmtree(staging)
        if not keep_aside:
            _rmtree(aside)
    _await_visible_in_containers(p)


def recover(p: Paths) -> None:
    """Deterministic recovery from an interrupted restore (a crash or failed rollback between the moves).
    With one `.aside-*`: if a live tree is missing, the swap did not finish, so roll back: every tree held
    aside goes back (a restored tree in its way is discarded). If both live trees exist and the aside holds
    both old ones, the swap finished and only cleanup is left. Staging dirs are always discarded. Any other
    shape (several asides, a live tree missing with no copy aside) raises InterruptedRestore — never guesses."""
    if not p.base.is_dir():
        return
    asides = sorted(x for x in p.base.iterdir() if x.name.startswith(".aside-"))
    stagings = sorted(x for x in p.base.iterdir() if x.name.startswith(".restore-"))
    if len(asides) > 1:
        raise gitops.InterruptedRestore(f"{p.base}: several interrupted restores {[a.name for a in asides]}")
    live = {"home": p.home, "work": p.work}
    for a in asides:
        held = {n for n in live if os.path.lexists(a / n)}
        missing = {n for n in live if not os.path.lexists(live[n])}
        if missing:
            if not missing <= held:
                raise gitops.InterruptedRestore(f"{p.base}: {sorted(missing)} missing and not held in {a.name}")
            for n in sorted(held):
                if os.path.lexists(live[n]):
                    live[n].rename(a / f"discard-{n}-{uuid.uuid4().hex[:8]}")
                (a / n).rename(live[n])
        elif held and held != set(live):
            raise gitops.InterruptedRestore(f"{p.base}: {a.name} holds only {sorted(held)} with both trees live")
        _rmtree(a)
    for s in stagings:
        _rmtree(s)
    if any(not os.path.lexists(x) for x in live.values()) and (asides or stagings):
        raise gitops.InterruptedRestore(f"{p.base}: home or work still missing after recovery")


PROBE_SECONDS = 5.0
PROBE_STOP_GRACE = 2         # a timed-out probe is stopped with this grace, not docker's default 30 s


def _await_visible_in_containers(p: Paths, timeout: float = 60.0) -> None:
    """Docker Desktop's file sharing can serve a just-replaced bind-mount source as the old, deleted directory
    for about a second (observed: the first git container after a swap saw an empty /work). Every restored
    file is a new inode, so once a container sees a fresh token at both new roots it sees the whole restored
    tree. The tokens sit at the mount roots, outside the repo, so a lingering cached entry is harmless.
    Gives up with RuntimeError once `timeout` seconds have passed. Each probe is capped at PROBE_SECONDS, and a
    probe that hits the cap is stopped with PROBE_STOP_GRACE seconds' grace before `docker rm -f`, so the worst
    case is `timeout + PROBE_SECONDS + PROBE_STOP_GRACE`, plus one 0.25 s pause and the `docker stop`/`rm`
    round-trips."""
    token = f".bk-restored-{uuid.uuid4().hex}"
    (p.work / token).touch(); (p.home / token).touch()
    base = gitops.spec(p, [])
    s = dataclasses.replace(base, name=base.name.replace("bk-git-", "bk-restore-", 1),
                            mounts=[Mount(p.work, "/work", True), Mount(p.home, p.container_home, True)],
                            cmd=["test", "-e", f"/work/{token}", "-a", "-e", f"{p.container_home}/{token}"])
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                ok = docker.run(dataclasses.replace(s, name=f"{s.name}-{uuid.uuid4().hex[:4]}"),
                                timeout=PROBE_SECONDS, stop_grace=PROBE_STOP_GRACE).returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
            if ok:
                return
            if time.monotonic() >= deadline:
                raise docker.ContainerError(f"restored {p.base} not visible to containers after {timeout:.0f}s")
            time.sleep(0.25)
    finally:
        (p.work / token).unlink(missing_ok=True); (p.home / token).unlink(missing_ok=True)


def export(p: Paths, sha: str, dest: Path) -> None:
    """The committed tree at `sha`, extracted in a container (gitops.export_tree). Host readers of `dest`
    must walk it without following links (e.g. transcripts.safe_files)."""
    gitops.export_tree(p, sha, dest)


def bundle(p: Paths, dest: Path) -> Path:
    return gitops.bundle(p, dest)


def github_plan(pass_: str) -> list[str]:
    """The `gh repo create` commands for the owner to run, for the active arms (parked ones have no repo), plus each
    GitHub-tracker arm's private N.a discovery repo (final fix batch A3). Runs nothing."""
    out = []
    for arm in config.active_arms():
        a = config.load_arm(arm)
        out.append(f'gh repo create {github_slug(pass_, arm)} --private '
                   f'--description "bakeoff-specs arm: {a.tool} {a.version} ({pass_})"')
    for arm in config.active_arms():
        if (disc := config.github_disc_slug(pass_, arm)):
            a = config.load_arm(arm)
            out.append(f'gh repo create {disc} --private '
                       f'--description "bakeoff-specs arm: {a.tool} {a.version} ({pass_}, N.a discovery tracker)"')
    return out


def pat_instructions(pass_: str) -> list[str]:
    """One fine-grained PAT per GitHub-tracker arm (OD16), and one for its N.a discovery repo (A3)."""
    out = []
    for arm in config.active_arms():
        if config.load_arm(arm).tracker != "github":
            continue
        out.append(f"{arm}: Create a fine-grained token: resource owner {ORG}; repository access: only "
                   f"`{github_slug(pass_, arm)}`; permissions: Issues read/write, Metadata read; "
                   f"**expiration: 45 days**. Store it with `security add-generic-password "
                   f"-s bakeoff-gh-{pass_}-{arm} -a \"$USER\" -w`.")
        if (disc := config.github_disc_slug(pass_, arm)):
            out.append(f"{arm} (N.a discovery): Create a fine-grained token: resource owner {ORG}; repository "
                       f"access: only `{disc}`; permissions: Issues read/write, Metadata read; **expiration: 45 "
                       f"days**. Store it with `security add-generic-password -s bakeoff-gh-{pass_}-disc-{arm} "
                       f"-a \"$USER\" -w`.")
    return out


def github_verify(pass_: str) -> dict:
    """Every active arm's repo, and every GitHub-tracker arm's N.a discovery repo as `<arm>-disc` (A3)."""
    res: dict = {}
    repos = [(arm, github_slug(pass_, arm)) for arm in config.active_arms()]
    repos += [(f"{arm}-disc", d) for arm in config.active_arms() if (d := config.github_disc_slug(pass_, arm))]
    for key, slug in repos:
        r = subprocess.run(["gh", "repo", "view", slug, "--json",
                            "visibility,hasIssuesEnabled,isEmpty"], capture_output=True, text=True)
        res[key] = json.loads(r.stdout) if r.returncode == 0 else {"error": r.stderr.strip()}
    r = subprocess.run(["gh", "repo", "list", ORG, "--visibility", "public", "--json", "name", "--limit", "500"],
                       capture_output=True, text=True)
    res["_public_repos"] = [x["name"] for x in json.loads(r.stdout)] if r.returncode == 0 else ["<gh error>"]
    return res


def verify_ok(res: dict) -> bool:
    """Every repo exists, is private, has issues enabled and is empty; no troupe-run repo is public (G7)."""
    arms = [v for k, v in res.items() if not k.startswith("_")]
    return not res.get("_public_repos", ["<missing>"]) and all(
        v.get("visibility") == "PRIVATE" and v.get("hasIssuesEnabled") and v.get("isEmpty") for v in arms)


GH_ENV_STRIP = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_REPO", "GH_ENTERPRISE_TOKEN")


def _gh(argv: list[str]) -> subprocess.CompletedProcess:
    """`gh` on the host with the owner's own login (as tracker._gh): no token/host/repo overrides from the
    environment and a neutral empty cwd."""
    import tempfile
    env = {k: v for k, v in os.environ.items() if k not in GH_ENV_STRIP}
    with tempfile.TemporaryDirectory(prefix="bakeoff-gh-") as cwd:
        return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd, timeout=120)


def repo_gaps(slug: str) -> list[str]:
    """What stops `slug` being used as an arm tracker repo (Task 26 pre-flight), by the owner's own `gh`: not found
    (or not visible to the owner's login), not private, issues disabled. [] when it is ready. Reads only."""
    try:
        r = _gh(["gh", "repo", "view", slug, "--json", "visibility,hasIssuesEnabled"])
    except subprocess.TimeoutExpired:
        return [f"GitHub repo {slug}: could not check (gh timed out)"]
    if r.returncode != 0:
        return [f"GitHub repo {slug}: not found (or not visible to your gh login; gh exit {r.returncode}): "
                f"{r.stderr.strip()[:200]}"]
    try:
        v = json.loads(r.stdout or "{}")
        if not isinstance(v, dict):
            raise ValueError("not a JSON object")
    except ValueError:
        return [f"GitHub repo {slug}: could not check (gh returned malformed JSON)"]
    out = []
    vis = str(v.get("visibility", "")).upper()
    if vis != "PRIVATE":
        out.append(f"GitHub repo {slug}: is {vis or 'of unknown visibility'}, must be PRIVATE")
    if not v.get("hasIssuesEnabled"):
        out.append(f"GitHub repo {slug}: issues are disabled")
    return out


def issue_gaps(slug: str, ignore_title: str) -> list[str]:
    """Task 26 fix round 1: a repo that must start with an empty tracker. Every issue (any state) whose title is not
    exactly `ignore_title` (the live probe's closed write test) is a gap, reported with its count. A gh timeout,
    failure or malformed JSON is a gap too, never a traceback."""
    try:
        r = _gh(["gh", "issue", "list", "--repo", slug, "--state", "all", "--limit", "1000", "--json", "number,title"])
    except subprocess.TimeoutExpired:
        return [f"GitHub repo {slug}: could not list its issues (gh timed out)"]
    if r.returncode != 0:
        return [f"GitHub repo {slug}: could not list its issues (gh exit {r.returncode}): {r.stderr.strip()[:200]}"]
    try:
        issues = json.loads(r.stdout or "[]")
        if not isinstance(issues, list):
            raise ValueError("not a JSON list")
    except ValueError:
        return [f"GitHub repo {slug}: could not list its issues (gh returned malformed JSON)"]
    other = [i for i in issues if not (isinstance(i, dict) and i.get("title") == ignore_title)]
    if not other:
        return []
    return [f"GitHub repo {slug}: holds {len(other)} issue(s) from an earlier run (any state); delete them "
            f"(`gh issue delete <n> --repo {slug}`) or recreate the repo (and its PAT)"]


def ensure_private_repo(slug: str, description: str) -> str:
    """OWNER (2026-09-30): the close-out repo exists and is private. "created" (made with `--private`) or
    "exists"; an existing repo that is not private is reported as "exists-<visibility>" and left alone — the
    runner never changes a visibility and never publishes to a public repo."""
    r = _gh(["gh", "repo", "view", slug, "--json", "visibility"])
    if r.returncode == 0:
        vis = str(json.loads(r.stdout or "{}").get("visibility", "")).upper()
        return "exists" if vis == "PRIVATE" else f"exists-{vis.lower() or 'unknown'}"
    c = _gh(["gh", "repo", "create", slug, "--private", "--description", description])
    if c.returncode != 0:
        raise RuntimeError(f"gh repo create {slug} failed ({c.returncode}): {c.stderr.strip()[:300]}")
    return "created"


def publish(p: Paths, pass_: str, ask, scan, slug: str | None = None) -> bool:
    """Push refs/heads/main via a host bare clone of a bundle made in a container (review S-1).
    `scan(tree, history) -> list[Finding]` is `secrets.scan_publish` (Task 21, review S-2): `tree` is the tip
    tree of THIS clone's main and `history` the `git fast-export` stream of everything reachable from it
    (None if the export failed — the scanner fails closed), both made in network-less containers. Any finding
    raises `secrets.SecretFound` ("secret-in-publish") naming where, never what, and nothing is pushed."""
    from runner import secrets
    slug = slug or github_slug(pass_, p.arm)          # close-out passes the final repo (OWNER)
    if not slug:
        return False
    # A fresh directory per attempt: the bundle is written through a bind mount, and a replaced mount source
    # can be served stale by Docker Desktop (see `_await_visible_in_containers`).
    root = p.scratch / "publish"
    _rmtree(root)
    work = root / uuid.uuid4().hex[:12]; work.mkdir(parents=True)
    b = gitops.bundle(p, work / "main.bundle", refs=("refs/heads/main",))
    bare = work / "clone.git"
    gitops.clone_bundle_bare(b, bare)                   # host: validated bundle -> config-free bare clone
    tree = gitops.bare_tree(p, bare, "main", work / "tree")   # scan input: THIS clone's main, extracted in a
                                                              # container; the scanner never follows links
    [history] = gitops.fast_export(p, bare, ["."], work / "history", revs=("refs/heads/main",))
    findings = scan(tree, history)
    if findings:
        raise secrets.SecretFound("secret-in-publish", findings)
    if not ask(f"Push main of {p.arm} ({pass_}) to {slug}? [y/N] "):
        return False
    gitops.push_from_bare(bare, f"https://github.com/{slug}.git")
    return True
