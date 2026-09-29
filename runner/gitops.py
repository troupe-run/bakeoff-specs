"""Git operations — the ONLY runner module that builds a git argv (review S-1; enforced by a test).

An arm runs with `bypassPermissions` and read-write access to its repo, including `.git/config` and
`.git/hooks`. Any host-side git command on that repo could execute host commands as the owner
(`core.fsmonitor`, `diff.external`, textconv/filter drivers, hooks, `credential.helper`/`core.sshCommand`,
`include.path`/`includeIf`). So every git command that touches an arm repo runs through `spec()`: inside a
`--network none`, read-only-root container of the arm's own image, with system/global config ignored. Reads
also mount the tree read-only and disable hooks and fsmonitor; writes keep hooks (a real developer's commit
runs them — e.g. beads' `bd` hooks — and the sandbox contains them).

Host-side git exists only in the helpers at the bottom, and none of them takes an arm's `Paths`: read-only
`ls-remote` against public remotes, the harness repo itself, and a bare clone of a bundle made in a container
(a bundle carries objects and refs only — no config, no hooks; validated before git reads it), which is
what `repo.publish` pushes from. The host never untars an arm tree: extraction happens in containers.
"""
from __future__ import annotations
import dataclasses, json, os, stat, subprocess, uuid
from dataclasses import dataclass
from pathlib import Path
from runner import config, docker
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT

IDENTITY = ("Developer", "developer@troupe.run")            # one neutral identity for every arm (review G9)
TEAMMATE = ("Sam Teammate", "sam.teammate@troupe.run")
ORIGIN = "/home/actor/origin.git"                            # every arm's local bare origin (owner answer, B4)
VERSION_PROBE = ["git", "--version"]                         # images.py's version probe (argv lives here, S-1)
READ_CFG = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "safe.directory=*",
            "-c", "diff.external=", "-c", "core.pager=cat", "-c", "i18n.logOutputEncoding=UTF-8"]
WRITE_CFG = ["-c", "safe.directory=*", "-c", "core.pager=cat", "-c", "commit.gpgsign=false"]


def image_for(arm: str) -> str:
    a = config.load_arm(arm)
    return config.load_pins().images["dryrun"] if a.dry else a.image


def spec(p: Paths, argv: list[str], *, write: bool = False, env: dict | None = None,
         out_dir: Path | None = None) -> RunSpec:
    """Pure: the container that runs `git -C <repo> <cfg> <argv>` for arm `p`."""
    mounts = [Mount(p.work, "/work", not write)]
    if write:                       # a real commit runs the repo's hooks, which may use $HOME; origin lives there
        mounts.append(Mount(p.home, p.container_home, False))
    if out_dir is not None:
        mounts.append(Mount(out_dir, "/out", False))
    e = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
         "HOME": p.container_home if write else "/tmp", **({} if write else {"GIT_OPTIONAL_LOCKS": "0"}),
         **(env or {})}
    return RunSpec(name=f"bk-git-{p.pass_}-{p.arm}-{uuid.uuid4().hex[:8]}", image=image_for(p.arm),
                   label=f"bakeoff.run={p.pass_}/{p.arm}", network="none", mounts=mounts, env=e,
                   workdir="/work", cmd=["git", "-C", p.container_repo, *(WRITE_CFG if write else READ_CFG), *argv],
                   stdin=False, limits=config.load_pins().limits, proxy=False)


class InterruptedRestore(RuntimeError):
    """An arm's base holds a leftover `.aside-*`/`.restore-*` from an interrupted `repo.restore`: its home or
    work may be the wrong tree, or missing. Nothing may touch it until `repo.recover(p)` has run."""


def check_trees(p: Paths) -> None:
    base = p.base
    if base.is_dir() and (left := sorted(x.name for x in base.iterdir() if x.name.startswith((".aside-", ".restore-")))):
        raise InterruptedRestore(f"{base}: interrupted restore {left}; run repo.recover first")


def git(p: Paths, *args: str, write: bool = False, env: dict | None = None, input: bytes | None = None,
        out_dir: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    check_trees(p)
    s = spec(p, list(args), write=write, env=env, out_dir=out_dir)
    if input is not None:
        s = dataclasses.replace(s, stdin=True)
    r = docker.run(s, input=input, timeout=600)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed in container ({r.returncode}): "
                           f"{r.stderr.decode(errors='replace')[:400]}")
    return r


def _out(r: subprocess.CompletedProcess) -> str:
    return r.stdout.decode(errors="replace").strip()


def _who_env(who: tuple[str, str]) -> dict[str, str]:
    return {"GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1],
            "GIT_COMMITTER_NAME": who[0], "GIT_COMMITTER_EMAIL": who[1]}


# ---- reads (tree mounted read-only; hooks, fsmonitor, textconv and external diff off) --------------------
def head(p: Paths) -> str:
    return _out(git(p, "rev-parse", "HEAD"))


def main_sha(p: Paths) -> str | None:
    r = git(p, "rev-parse", "--verify", "-q", "refs/heads/main", check=False)
    return _out(r) or None


@dataclass(frozen=True)
class RepoState:
    branch: str
    dirty: bool
    head: str
    main: str | None
    head_in_main: bool


_STATE_SH = r"""cd "$1"; g() { git -c safe.directory='*' -c core.hooksPath=/dev/null -c core.fsmonitor=false "$@"; }
b=$(g branch --show-current); d=$(g status --porcelain | head -c 1); h=$(g rev-parse HEAD)
m=$(g rev-parse --verify -q refs/heads/main || true)
if [ -n "$m" ] && g merge-base --is-ancestor "$h" "$m"; then a=true; else a=false; fi
jq -cn --arg b "$b" --arg d "$d" --arg h "$h" --arg m "$m" --argjson a $a \
  '{branch:$b, dirty:($d!=""), head:$h, main:(if $m=="" then null else $m end), head_in_main:$a}'"""


def state(p: Paths) -> RepoState:
    """One container for all five facts (same read config as `spec`, via a small script)."""
    check_trees(p)
    s = dataclasses.replace(spec(p, []), cmd=["bash", "-c", _STATE_SH, "state", p.container_repo])
    r = docker.run(s, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git state failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
    return RepoState(**json.loads(r.stdout))


def archive(p: Paths, sha: str) -> bytes:
    return git(p, "archive", "--format=tar", sha).stdout


def grep_files(p: Paths, sha: str, pattern: str, pathspec: str = ":!*.py") -> list[str]:
    r = git(p, "grep", "-l", "-F", "-e", pattern, sha, "--", pathspec, check=False)
    return sorted(l.split(":", 1)[1] for l in _out(r).splitlines() if ":" in l)


def _nul_fields(r: subprocess.CompletedProcess, n: int) -> list[list[str]]:
    """`git log -z` output with NUL between fields: git ends every record with exactly one NUL, and NUL can
    never occur in a sha, an author name or a message (git truncates messages at NUL). Output is forced to
    UTF-8 (READ_CFG and `--encoding=UTF-8`), so an arm-set `i18n.logOutputEncoding=UTF-16LE` cannot inject
    NULs. Exactly one trailing NUL is removed, so an empty last field survives."""
    raw = r.stdout.decode(errors="replace")
    if not raw:
        return []
    if not raw.endswith("\0"):
        raise RuntimeError("git log -z: output does not end with a record NUL")
    parts = raw[:-1].split("\0")
    if len(parts) % n:
        raise RuntimeError(f"git log: {len(parts)} NUL-separated fields is not a multiple of {n}")
    return [parts[i:i + n] for i in range(0, len(parts), n)]


def log(p: Paths, a: str, b: str) -> list[dict]:
    r = git(p, "log", "-z", "--encoding=UTF-8", "--format=%H%x00%an%x00%s", f"{a}..{b}")
    return [dict(zip(("sha", "author", "subject"), f)) for f in _nul_fields(r, 3)]


_SEPS = str.maketrans({"\x1e": "\ufffd", "\x1f": "\ufffd"})


def commits_between(p: Paths, a: str, b: str) -> str:
    r"""Records `sha\x1fmessage\x1e` (message = subject, newline, body; trailing whitespace stripped), newest
    first. Parsed exactly from NUL-delimited output; any \x1e or \x1f inside a message is replaced by U+FFFD,
    so splitting on \x1e then on the first \x1f is always exact."""
    r = git(p, "log", "-z", "--encoding=UTF-8", "--format=%H%x00%s%n%b", f"{a}..{b}")
    return "".join(f"{sha}\x1f{msg.rstrip().translate(_SEPS)}\x1e" for sha, msg in _nul_fields(r, 2))


def diffstat(p: Paths, a: str, b: str) -> str:
    return _out(git(p, "diff", "--no-textconv", "--no-ext-diff", "--stat", a, b))


def numstat(p: Paths, a: str, b: str) -> list[tuple[int, int, str]]:
    out = []
    for l in _out(git(p, "diff", "--no-textconv", "--no-ext-diff", "--numstat", a, b)).splitlines():
        ad, de, f = l.split("\t", 2)
        out.append((int(ad) if ad.isdigit() else 0, int(de) if de.isdigit() else 0, f))
    return out


def worktree_diffstat(p: Paths) -> str:
    return _out(git(p, "diff", "--no-textconv", "--no-ext-diff", "--stat", "HEAD"))


def show(p: Paths, sha: str) -> str:
    return git(p, "show", "--no-textconv", "--no-ext-diff", "--format=fuller", sha).stdout.decode(errors="replace")


def porcelain(p: Paths) -> str:
    return git(p, "status", "--porcelain", "-uall").stdout.decode(errors="replace")


def ls_files(p: Paths, sha: str) -> list[str]:
    return _out(git(p, "ls-tree", "-r", "--name-only", sha)).splitlines()


_EXPORT_SH = r"""set -euo pipefail
git -C "$1" -c core.hooksPath=/dev/null -c core.fsmonitor=false -c safe.directory='*' archive --format=tar "$2" \
  | tar -x -f - -C /out --no-same-owner"""


def export_tree(p: Paths, sha: str, dest: Path) -> None:
    """The committed tree at `sha`, extracted INSIDE a read container into `dest` (mounted at /out). The host
    never untars an arm tree: links in it are just data, written as links, contained by the sandbox."""
    check_trees(p)
    dest.mkdir(parents=True, exist_ok=True)
    s = dataclasses.replace(spec(p, [], out_dir=dest), cmd=["bash", "-c", _EXPORT_SH, "export", p.container_repo, sha])
    r = docker.run(s, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"export failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")


_BARE_TREE_SH = r"""set -euo pipefail
git -C /in/bare.git -c core.hooksPath=/dev/null -c safe.directory='*' archive --format=tar "$1" \
  | tar -x -f - -C /out --no-same-owner"""


def bare_tree(p: Paths, bare: Path, ref: str, dest: Path) -> Path:
    """The tree of `ref` in the host bare clone that publish will push, extracted INSIDE a network-less
    container: the bare clone is mounted read-only, and only `dest` (at /out) is writable. So the scanned tree
    is exactly what gets pushed."""
    dest.mkdir()
    s = dataclasses.replace(spec(p, []), mounts=[Mount(bare, "/in/bare.git", True), Mount(dest, "/out", False)],
                            cmd=["bash", "-c", _BARE_TREE_SH, "bare-tree", ref])
    r = docker.run(s, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"bare tree failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
    return dest


_FAST_EXPORT_SH = r"""set -uo pipefail
n=$1; shift; revs=("${@:1:$n}"); shift "$n"; i=0
for d in "$@"; do
  i=$((i+1))
  g() { git --git-dir="/in/$d" -c core.hooksPath=/dev/null -c core.fsmonitor=false -c safe.directory='*' "$@"; }
  refs=$(g for-each-ref --count=1 --format=x) || continue          # unreadable: no file -> unscannable
  if [ -z "$refs" ]; then : > "/out/$i.fe"; continue; fi            # no refs: nothing to export
  g fast-export --reencode=yes --signed-tags=verbatim --show-original-ids "${revs[@]}" > "/out/$i.fe.part" \
    && mv "/out/$i.fe.part" "/out/$i.fe"
  rm -f "/out/$i.fe.part"
done"""


def fast_export(p: Paths, root: Path, git_dirs: list[str], dest: Path, *,
                revs: tuple[str, ...] = ("--all", "--reflog")) -> list[Path | None]:
    """Every object reachable from `revs` in each git dir under `root` (paths relative to it), as a
    `git fast-export` stream — blobs, commit messages, identities, file and link names — for the secret scan
    (review S-2). ONE network-less container of the arm's image: `root` read-only at /in, `dest` the only
    writable mount. Result i is `dest/<i+1>.fe`, or None when that export failed (the scanner fails closed on
    None). A git dir with no refs exports as an empty stream."""
    check_trees(p)
    dest.mkdir(parents=True, exist_ok=True)
    base = spec(p, [])
    s = dataclasses.replace(base, name=base.name.replace("bk-git-", "bk-fe-", 1),
                            mounts=[Mount(root, "/in", True), Mount(dest, "/out", False)], workdir="/",
                            cmd=["bash", "-c", _FAST_EXPORT_SH, "fast-export", str(len(revs)), *revs, *git_dirs])
    r = docker.run(s, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"fast-export failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
    return [f if (f := dest / f"{i}.fe").is_file() and not f.is_symlink() else None
            for i in range(1, len(git_dirs) + 1)]


BUNDLE_HEADERS = (b"# v2 git bundle\n", b"# v3 git bundle\n")


def check_bundle(path: Path) -> None:
    """Before host git reads it: a regular file — not a link, directory or device —
    whose first line is a v2 or v3 git bundle header."""
    try:
        st = os.lstat(path)
    except OSError as e:
        raise ValueError(f"bundle {path}: {e}") from e
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"bundle {path}: not a regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        head_ = os.read(fd, 32)
    finally:
        os.close(fd)
    if not head_.startswith(BUNDLE_HEADERS):
        raise ValueError(f"bundle {path}: no git bundle header (got {head_[:20]!r})")


def bundle(p: Paths, host_dest: Path, refs: tuple[str, ...] = ("--all",)) -> Path:
    """Made in a read container; only `host_dest`'s directory is mounted writable (at /out)."""
    host_dest.parent.mkdir(parents=True, exist_ok=True)
    git(p, "bundle", "create", f"/out/{host_dest.name}", *refs, out_dir=host_dest.parent)
    check_bundle(host_dest)
    return host_dest


# ---- writes (tree and home read-write; the repo's hooks run, contained) ----------------------------------
def init_repo(p: Paths) -> str:
    """`main` with one empty commit, pushed upstream to a local bare origin in the arm's home (owner answer,
    preflight B4). The GitHub URL is never the origin: publishing is a separate, owner-approved step."""
    git(p, "init", "-q", "-b", "main", write=True)
    git(p, "commit", "-q", "--allow-empty", "-m", "Initial commit", write=True, env=_who_env(IDENTITY))
    git(p, "init", "-q", "--bare", "-b", "main", ORIGIN, write=True)
    git(p, "remote", "add", "origin", ORIGIN, write=True)
    git(p, "push", "-q", "-u", "origin", "main", write=True)
    return head(p)


def commit_all(p: Paths, who: tuple[str, str], message: str) -> str:
    env = _who_env(who)
    git(p, "add", "-A", write=True, env=env)
    git(p, "commit", "-q", "-m", message, write=True, env=env)
    return head(p)


def checkout_paths(p: Paths, paths_: list[str]) -> None:
    if paths_:
        git(p, "checkout", "--", *paths_, write=True)


def remove_untracked(p: Paths, paths_: list[str]) -> None:
    if paths_:
        git(p, "clean", "-f", "-q", "--", *paths_, write=True)


# ---- host-side helpers: never an arm repo (public remotes, the harness repo, a bundle's bare clone) --------
class TagNotFound(RuntimeError):
    """The remote was reached and answered, but has no such tag. Callers may park the plugin rather than
    pinning to nothing (review B2: e.g. `bmad-code-org/bmad-plugins` carries no tags at all)."""


class GitRemoteUnavailable(RuntimeError):
    """We couldn't even ask the remote (network unreachable, DNS failure, repo not found, the `git`
    call timed out or the subprocess itself failed to start). Fatal — never a reason to park a plugin:
    unlike `TagNotFound`, this doesn't mean the tag is absent, only that we don't know yet (review
    fix-round-1 item 3: a transient failure here must not be mistaken for a genuinely missing tag)."""


def _host_env() -> dict[str, str]:
    """Environment for a host-side `git` call: no interactive credential prompt, no local/global git
    config leaking in. This call is read-only and must be reproducible regardless of the operator's own
    git setup (aliases, credential helpers, includeIf rules, ...)."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}


def ls_remote_tag(repo_slug: str, tag: str) -> str:
    """The commit SHA `tag` points at on `https://github.com/<repo_slug>` (peeled to the target commit if
    the tag is annotated). Read-only, host-side, no clone.

    Raises `GitRemoteUnavailable` (fatal, never park) if we couldn't reach the remote at all — a nonzero
    exit from `git ls-remote` means the connection or the repo lookup itself failed (network unreachable,
    DNS failure, repository not found, ...), not that the tag is absent; the same for a `subprocess.run`
    failure (timeout, `git` not on PATH). Raises `TagNotFound` (may park) only when the remote answered
    successfully and simply has no such tag (review fix-round-1 item 3).

    Queries every tag rather than passing `tag` as a refspec pattern: `git ls-remote --tags <url> <tag>`
    matches only the tag ref itself and drops the server's synthetic `^{}` peeled-commit line for an
    annotated tag, silently returning the tag *object* SHA instead of the commit it points at."""
    try:
        r = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{repo_slug}"],
                            capture_output=True, text=True, env=_host_env(), timeout=30)
    except (subprocess.SubprocessError, OSError) as e:
        raise GitRemoteUnavailable(f"{repo_slug}@{tag}: could not run git ls-remote: {e}") from e
    if r.returncode != 0:
        raise GitRemoteUnavailable(f"{repo_slug}@{tag}: git ls-remote failed: {r.stderr.strip()}")
    refs = dict(line.split(maxsplit=1)[::-1] for line in r.stdout.splitlines() if line.strip())
    want = f"refs/tags/{tag}"
    sha = refs.get(f"{want}^{{}}") or refs.get(want)
    if not sha:
        raise TagNotFound(f"{repo_slug}@{tag}: no such tag on the remote")
    return sha


def commit_harness_file(path: Path, message: str) -> None:
    """The harness repo (this repo) only. Commits exactly one path, never whatever else is staged (review S-8)."""
    subprocess.run(["git", "-C", str(REPO_ROOT), "add", "--", str(path)], check=True)
    subprocess.run(["git", "-C", str(REPO_ROOT), "commit", "-q", "-m", message, "--", str(path)], check=True)


def harness_is_clean(path: Path) -> bool:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "diff", "--quiet", "--", str(path)])
    return r.returncode == 0


def staged_files() -> list[Path]:
    """The harness repo only (the pre-commit hook's `runner scan --staged`): paths staged for the next commit,
    deletions excluded. Absolute, under REPO_ROOT."""
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "diff", "--cached", "--name-only", "-z", "--diff-filter=d"],
                       capture_output=True, check=True)
    return [REPO_ROOT / os.fsdecode(n) for n in r.stdout.split(b"\0") if n]


def clone_bundle_bare(bundle_path: Path, dest: Path) -> None:
    """Host: bare clone of a bundle made in a container — objects and refs only, no config or hooks. System
    and global config are ignored too, so no template dir or include can add any."""
    check_bundle(bundle_path)
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "-q", "--bare", str(bundle_path), str(dest)],
                   check=True, env=_host_env(), capture_output=True)


def push_from_bare(bare: Path, url: str, ref: str = "main") -> None:
    """Uses the owner's own git credentials (system/global config is read on purpose); the bare clone's own
    config is git's default, and hooks are off."""
    subprocess.run(["git", "-C", str(bare), "-c", "core.hooksPath=/dev/null", "push", url, f"{ref}:{ref}"],
                   check=True)
