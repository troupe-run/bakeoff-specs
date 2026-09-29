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

__all__ = ["ORG", "github_slug", "init", "head", "snapshot", "restore", "export", "bundle", "github_plan",
           "github_verify", "verify_ok", "publish", "pat_instructions"]


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
        raise RuntimeError(f"{what} failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")


_SNAPSHOT_SH = r"""set -euo pipefail
tar -c -f "/snap/$1.partial" -C /src home work
mv -f "/snap/$1.partial" "/snap/$1"
"""


def snapshot(p: Paths, step: int | str) -> Path:
    """Tar of the arm-controlled trees (home — including the bare origin — and work), made in a container
    with both mounted read-only. GNU tar stores links as links and never follows them."""
    p.snapshots.mkdir(parents=True, exist_ok=True)
    name = _snap_name(step)
    _run(_tar_spec(p, [Mount(p.home, "/src/home", True), Mount(p.work, "/src/work", True),
                       Mount(p.snapshots, "/snap", False)], _SNAPSHOT_SH, name, tag="snap"), f"snapshot {name}")
    return p.snapshots / name


_RESTORE_SH = r"""set -euo pipefail
tar -x -f "/snap/$1" -C /out --no-same-owner
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


def restore(p: Paths, step: int | str) -> None:
    """Extract the snapshot INSIDE a container into a fresh staging dir; then swap by rename-aside (current
    trees moved aside, restored trees moved in, aside deleted last). A refused or failed extract, or a failure
    mid-swap, leaves (or puts back) the current home and work, so the arm is never left without them."""
    src = p.snapshots / _snap_name(step)
    if not src.is_file() or src.is_symlink():
        raise FileNotFoundError(f"no snapshot {src}")
    run_id = uuid.uuid4().hex[:12]
    staging, aside = p.base / f".restore-{run_id}", p.base / f".aside-{run_id}"
    staging.mkdir(); aside.mkdir()
    try:
        _run(_tar_spec(p, [Mount(p.snapshots, "/snap", True), Mount(staging, "/out", False)],
                       _RESTORE_SH, src.name, tag="restore"), f"restore {src.name}")
        moved: list[tuple[Path, Path]] = []
        try:
            for live, name in ((p.home, "home"), (p.work, "work")):
                if os.path.lexists(live):
                    live.rename(aside / name); moved.append((aside / name, live))
            (staging / "home").rename(p.home)
            (staging / "work").rename(p.work)
        except BaseException:
            for held, live in reversed(moved):              # undo: put the previous trees back
                if os.path.lexists(live):
                    live.rename(staging / f"failed-{live.name}")
                held.rename(live)
            raise
    finally:
        _rmtree(staging); _rmtree(aside)
    _await_visible_in_containers(p)


PROBE_SECONDS = 5.0


def _await_visible_in_containers(p: Paths, timeout: float = 60.0) -> None:
    """Docker Desktop's file sharing can serve a just-replaced bind-mount source as the old, deleted directory
    for about a second (observed: the first git container after a swap saw an empty /work). Every restored
    file is a new inode, so once a container sees a fresh token at both new roots it sees the whole restored
    tree. The tokens sit at the mount roots, outside the repo, so a lingering cached entry is harmless.
    Gives up with RuntimeError once `timeout` seconds have passed; each probe container is itself capped at
    PROBE_SECONDS, so the total wait is at most `timeout + PROBE_SECONDS` plus one 0.25 s pause."""
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
                                timeout=PROBE_SECONDS).returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
            if ok:
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f"restored {p.base} not visible to containers after {timeout:.0f}s")
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
    """The `gh repo create` commands for the owner to run. Runs nothing."""
    out = []
    for arm in config.all_arms():
        a = config.load_arm(arm)
        out.append(f'gh repo create {github_slug(pass_, arm)} --private '
                   f'--description "bakeoff-specs arm: {a.tool} {a.version} ({pass_})"')
    return out


def pat_instructions(pass_: str) -> list[str]:
    """One fine-grained PAT per GitHub-tracker arm (OD16)."""
    out = []
    for arm in config.all_arms():
        if config.load_arm(arm).tracker != "github":
            continue
        out.append(f"{arm}: Create a fine-grained token: resource owner {ORG}; repository access: only "
                   f"`{github_slug(pass_, arm)}`; permissions: Issues read/write, Metadata read; "
                   f"**expiration: 45 days**. Store it with `security add-generic-password "
                   f"-s bakeoff-gh-{pass_}-{arm} -a \"$USER\" -w`.")
    return out


def github_verify(pass_: str) -> dict:
    res: dict = {}
    for arm in config.all_arms():
        r = subprocess.run(["gh", "repo", "view", github_slug(pass_, arm), "--json",
                            "visibility,hasIssuesEnabled,isEmpty"], capture_output=True, text=True)
        res[arm] = json.loads(r.stdout) if r.returncode == 0 else {"error": r.stderr.strip()}
    r = subprocess.run(["gh", "repo", "list", ORG, "--visibility", "public", "--json", "name", "--limit", "500"],
                       capture_output=True, text=True)
    res["_public_repos"] = [x["name"] for x in json.loads(r.stdout)] if r.returncode == 0 else ["<gh error>"]
    return res


def verify_ok(res: dict) -> bool:
    """Every repo exists, is private, has issues enabled and is empty; no troupe-run repo is public (G7)."""
    arms = [v for k, v in res.items() if not k.startswith("_")]
    return not res.get("_public_repos", ["<missing>"]) and all(
        v.get("visibility") == "PRIVATE" and v.get("hasIssuesEnabled") and v.get("isEmpty") for v in arms)


def publish(p: Paths, pass_: str, ask, scan) -> bool:
    """Push refs/heads/main via a host bare clone of a bundle made in a container (review S-1).
    `scan(dir) -> list[findings]` is secrets.scan_tree (Task 21); any finding refuses the push."""
    slug = github_slug(pass_, p.arm)
    if not slug:
        return False
    # A fresh directory per attempt: the bundle is written through a bind mount, and a replaced mount source
    # can be served stale by Docker Desktop (see `_await_visible_in_containers`).
    root = p.scratch / "publish"
    _rmtree(root)
    work = root / uuid.uuid4().hex[:12]; work.mkdir(parents=True)
    b = gitops.bundle(p, work / "main.bundle", refs=("refs/heads/main",))
    tree = gitops.bundle_tree(p, b, "main", "tree")     # scan input, extracted in a container; the scanner
    bare = work / "clone.git"                           # walks it without following links (Task 21)
    gitops.clone_bundle_bare(b, bare)                   # host: validated bundle -> config-free bare clone
    findings = scan(tree)
    if findings:
        print(f"Refusing to publish {slug}: {len(findings)} secret finding(s): {findings[:5]}")
        return False
    if not ask(f"Push main of {p.arm} ({pass_}) to {slug}? [y/N] "):
        return False
    gitops.push_from_bare(bare, f"https://github.com/{slug}.git")
    return True
