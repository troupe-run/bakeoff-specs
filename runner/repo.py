"""Arm repo lifecycle: init, snapshots, restore, export, bundle, GitHub plan/verify, publish.

Every git command on an arm repo goes through `gitops` (containers; review S-1). This module never runs git
itself: host-side it only tars/untars arm trees (symlinks stored, never followed; restore with
`filter="data"`) and calls `gh` for the owner-facing GitHub plan and verification.
"""
from __future__ import annotations
import dataclasses, io, json, shutil, subprocess, tarfile, time, uuid
from pathlib import Path
from runner import config, docker, gitops
from runner.config import GITHUB_ORG as ORG, github_slug     # single source; re-exported (Task 5 / M4)
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


def snapshot(p: Paths, step: int | str) -> Path:
    """Host tar of arm-controlled trees (home — including the bare origin — and work): symlinks are stored as
    links, never followed (tarfile default)."""
    p.snapshots.mkdir(parents=True, exist_ok=True)
    out = p.snapshots / _snap_name(step)
    with tarfile.open(out, "w") as tf:
        tf.add(p.home, arcname="home"); tf.add(p.work, arcname="work")
    return out


def restore(p: Paths, step: int | str) -> None:
    """Extract into a temp dir first (filter="data" refuses links pointing outside, absolute paths, devices),
    so a refused snapshot leaves the current state untouched; then swap."""
    src, tmp = p.snapshots / _snap_name(step), p.base / ".restore-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        with tarfile.open(src) as tf:
            tf.extractall(tmp, filter="data")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(p.home); shutil.rmtree(p.work)
    (tmp / "home").rename(p.home); (tmp / "work").rename(p.work)
    tmp.rmdir()
    _await_visible_in_containers(p)


def _await_visible_in_containers(p: Paths, timeout: float = 60.0) -> None:
    """Docker Desktop's file sharing can serve a just-replaced bind-mount source as the old, deleted directory
    for about a second (observed: the first git container after a swap saw an empty /work). Every restored
    file is a new inode, so once a container sees a fresh token at both new roots it sees the whole restored
    tree. The tokens sit at the mount roots, outside the repo, so a lingering cached entry is harmless."""
    token = f".bk-restored-{uuid.uuid4().hex}"
    (p.work / token).touch(); (p.home / token).touch()
    base = gitops.spec(p, [])
    s = dataclasses.replace(base, name=base.name.replace("bk-git-", "bk-restore-", 1),
                            mounts=[docker.Mount(p.work, "/work", True), docker.Mount(p.home, p.container_home, True)],
                            cmd=["test", "-e", f"/work/{token}", "-a", "-e", f"{p.container_home}/{token}"])
    try:
        deadline = time.monotonic() + timeout
        while docker.run(dataclasses.replace(s, name=f"{s.name}-{uuid.uuid4().hex[:4]}"), timeout=60).returncode != 0:
            if time.monotonic() > deadline:
                raise RuntimeError(f"restored {p.base} not visible to containers after {timeout:.0f}s")
            time.sleep(0.25)
    finally:
        (p.work / token).unlink(missing_ok=True); (p.home / token).unlink(missing_ok=True)


def export(p: Paths, sha: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(gitops.archive(p, sha))) as tf:
        tf.extractall(dest, filter="data")


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
    shutil.rmtree(root, ignore_errors=True)
    work = root / uuid.uuid4().hex[:12]; work.mkdir(parents=True)
    b = gitops.bundle(p, work / "main.bundle", refs=("refs/heads/main",))
    bare = work / "clone.git"
    gitops.clone_bundle_bare(b, bare)
    tree = work / "tree"; tree.mkdir()
    with tarfile.open(fileobj=io.BytesIO(gitops.archive_from_bare(bare, "main"))) as tf:
        tf.extractall(tree, filter="data")
    findings = scan(tree)
    if findings:
        print(f"Refusing to publish {slug}: {len(findings)} secret finding(s): {findings[:5]}")
        return False
    if not ask(f"Push main of {p.arm} ({pass_}) to {slug}? [y/N] "):
        return False
    gitops.push_from_bare(bare, f"https://github.com/{slug}.git")
    return True
