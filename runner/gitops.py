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
from datetime import datetime, timezone
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
        raise docker.ContainerError(f"git {args[0]} failed in container ({r.returncode}): "
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
        raise docker.ContainerError(f"git state failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
    return RepoState(**json.loads(r.stdout))


# ---- the N.a discovery run's code check (Task 22, fix rounds 1-2, I-1) ---------------------------------------------
# Directories that are never authored code: excluded from the content hash (performance) and from the check.
NEVER_CODE = (".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "node_modules")


def never_code_pathspecs() -> list[str]:
    return [f":(exclude,glob)**/{d}/**" for d in NEVER_CODE]


# Read-only, and nothing an arm can leave in its repo makes it fail: files are hashed with `hash-object --no-filters`
# (no index, no object writes, no filter drivers run; paths fed as `./<path>` so a leading `"` is never C-unquoted);
# an untracked entry ending in `/` is an embedded repo (with or without a commit) and is reported as such; a name with
# a newline cannot go through `--stdin-paths` and is tagged like an embedded repo; baseline tips that no longer exist
# are dropped (`cat-file -e`) before `log`, and HEAD joins the tips (and the log range) only when it resolves (a
# detached HEAD is a tip; an orphan checkout has none). Output: seven sections, each `<byte length>\n<bytes>`, so no
# byte in a name can split them: [0] mode; [1] NUL paths of regular files; [2] their blob ids, one per line; [3] NUL
# embedded-repo dirs (and newline names); [4] NUL `path, link target` pairs; [5] `refname\tsha` lines (`HEAD\tsha`
# included); then with mode "base" [6] `ls-tree -r -z` of every tip, or with mode "check" [6] `log --raw -z` of every
# commit reachable from a branch or HEAD that no surviving baseline tip reaches.
_CONTENT_SH = r"""cd "$1"; mode="$2"; shift 2
g() { git -c safe.directory='*' -c core.hooksPath=/dev/null -c core.fsmonitor=false "$@"; }
set -e -o pipefail
ex=(); while IFS= read -r l; do [ -n "$l" ] && ex+=("$l"); done <<< "$BK_EXCLUDES"
t=$(mktemp -d)
g ls-files -z --cached --others --exclude-standard -- . "${ex[@]}" | sort -zu > "$t/all"
: > "$t/s1"; : > "$t/filesn"; : > "$t/s2"; : > "$t/s3"; : > "$t/s4"; : > "$t/s6"
printf '%s' "$mode" > "$t/s0"
while IFS= read -r -d '' f; do
  case "$f" in
    */) printf '%s\0' "$f" >> "$t/s3" ;;
    *$'\n'*) printf '%s\0' "$f" >> "$t/s3" ;;
    *) if [ -L "$f" ]; then printf '%s\0%s\0' "$f" "$(readlink -- "$f")" >> "$t/s4"
       elif [ -f "$f" ]; then printf '%s\0' "$f" >> "$t/s1"; printf './%s\n' "$f" >> "$t/filesn"; fi ;;
  esac
done < "$t/all"
if [ -s "$t/filesn" ]; then g hash-object --no-filters --stdin-paths < "$t/filesn" > "$t/s2"; fi
head=(); if h=$(g rev-parse -q --verify HEAD); then head=(HEAD); fi
{ g for-each-ref refs/heads --format='%(refname)%09%(objectname)'
  if [ -n "${head[*]}" ]; then printf 'HEAD\t%s\n' "$h"; fi; } > "$t/s5"
if [ "$mode" = base ]; then
  for sha in $(cut -f2 "$t/s5" | sort -u); do g ls-tree -r -z --full-tree "$sha"; done > "$t/s6"
else
  keep=(); for x in "$@"; do if g cat-file -e "$x^{commit}" 2>/dev/null; then keep+=("^$x"); fi; done
  g log --raw --no-renames --no-abbrev --format= -z --branches "${head[@]}" "${keep[@]}" -- . "${ex[@]}" > "$t/s6"
fi
for i in 0 1 2 3 4 5 6; do printf '%d\n' "$(wc -c < "$t/s$i")"; cat "$t/s$i"; done"""


def _sections(out: bytes, n: int = 7) -> list[bytes]:
    parts, pos = [], 0
    for _ in range(n):
        nl = out.index(b"\n", pos)
        size = int(out[pos:nl])
        parts.append(out[nl + 1:nl + 1 + size])
        pos = nl + 1 + size
    if pos != len(out):
        raise ValueError(f"git content state: {len(out) - pos} trailing bytes")
    return parts


def _blob_of_link(target: bytes) -> str:
    import hashlib
    return hashlib.sha1(b"blob %d\0" % len(target) + target).hexdigest()


def _content(p: Paths, mode: str, tips: list[str]) -> tuple[dict[str, set[str]], dict[str, str], dict[str, set[str]]]:
    """(working-tree pairs, branch tips, mode section pairs), each pairs map `path -> {blob}`."""
    check_trees(p)
    base = spec(p, [])
    s = dataclasses.replace(base, cmd=["bash", "-c", _CONTENT_SH, "content", p.container_repo, mode, *tips],
                            env={**base.env, "BK_EXCLUDES": "\n".join(never_code_pathspecs())})
    r = docker.run(s, timeout=600)
    if r.returncode != 0:
        raise docker.ContainerError(f"git content state failed in container ({r.returncode}): "
                                    f"{r.stderr.decode(errors='replace')[:400]}")
    try:
        parts = _sections(r.stdout)
    except ValueError as e:
        raise docker.ContainerError(f"git content state: unreadable output ({e})") from e
    if parts[0].decode() != mode:
        raise docker.ContainerError(f"git content state: mode {parts[0][:20]!r}, expected {mode}")
    dec = lambda b: b.decode(errors="surrogateescape")
    wt: dict[str, set[str]] = {}
    files = [dec(x) for x in parts[1].split(b"\0") if x]
    blobs = parts[2].decode().split()
    if len(files) != len(blobs):
        raise docker.ContainerError(f"git content state: {len(files)} files but {len(blobs)} blob ids")
    for f, b in zip(files, blobs):
        wt.setdefault(f, set()).add(b)
    for d in (x for x in parts[3].split(b"\0") if x):
        wt.setdefault(dec(d), set()).add("embedded")
    links = parts[4].split(b"\0")
    for path, target in zip(links[0::2], links[1::2]):
        if path:
            wt.setdefault(dec(path), set()).add(_blob_of_link(target))
    tips = dict(l.split("\t", 1) for l in parts[5].decode(errors="replace").splitlines() if "\t" in l)
    more: dict[str, set[str]] = {}
    recs = parts[6].split(b"\0")
    if mode == "base":                       # "<mode> <type> <sha>\t<path>"
        for rec in recs:
            if b"\t" in rec:
                meta, _, path = rec.partition(b"\t")
                more.setdefault(dec(path), set()).add(meta.split()[2].decode())
    else:                                    # ":<m> <m> <old> <new> <status>" then the path
        it = iter(recs)
        for rec in it:
            rec = rec.lstrip(b"\n")
            if rec.startswith(b":"):
                new, path = rec.split()[3].decode(), dec(next(it, b""))
                if path and set(new) != {"0"}:            # a deletion adds no content
                    more.setdefault(path, set()).add(new)
    return wt, {k: v.strip() for k, v in tips.items()}, more


def content_state(p: Paths) -> dict:
    """The N.a discovery run's baseline, taken at the attempt's start: `{"pairs": {path: [blob, ...]}, "tips":
    {ref: sha}}` — every blob at every path in the working tree (tracked or untracked, never ignored, never
    `NEVER_CODE`) and in every local branch tip's tree. Whatever an earlier step left behind is in it."""
    wt, tips, trees = _content(p, "base", [])
    pairs = {k: set(v) for k, v in wt.items()}
    for k, v in trees.items():
        pairs.setdefault(k, set()).update(v)
    return {"pairs": {k: sorted(v) for k, v in pairs.items()}, "tips": tips}


def changed_since(p: Paths, baseline: dict) -> list[str]:
    """Paths the arm authored since `baseline` (fix round 2 ruling): a path counts only when its content now — in the
    working tree, or in a commit reachable from a branch or HEAD that no baseline tip reaches (`log --raw`) — is a
    blob that was not at that path in the baseline. Committing or checking out leftovers, and touched-then-reverted
    files, therefore never count; deletions add no content and do not count. A new embedded repo counts as its
    `dir/`. Gaps: merge-only resolutions (a merge commit's own changes are not in `log --raw`), edits inside an
    embedded repo that was already there, edits to a file whose name contains a newline (tagged like an embedded
    repo, so only its appearance counts, not its content), and work in a linked worktree outside the repo
    directory."""
    wt, _, commits = _content(p, "check", sorted(set(baseline["tips"].values())))
    known = baseline["pairs"]
    out = set()
    for src in (wt, commits):
        for path, blobs in src.items():
            if any(b not in known.get(path, ()) for b in blobs):
                out.add(path)
    return sorted(out)


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


def ignored(p: Paths) -> list[str]:
    """Ignored paths in the worktree, as `status --ignored` lists them (a wholly ignored directory once, as
    `dir/`), sorted."""
    out = git(p, "status", "--porcelain", "--ignored=traditional", "--untracked-files=normal").stdout
    return sorted(l[3:] for l in out.decode(errors="replace").splitlines() if l.startswith("!! "))


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
        raise docker.ContainerError(f"export failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")


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
        raise docker.ContainerError(f"bare tree failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
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
        raise docker.ContainerError(f"fast-export failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:400]}")
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


def set_aside_to_main(p: Paths, message: str, label: str = "02") -> dict:
    """Before the step-2 hand edit (Task 23 ruling): the teammate commits on a clean `main`.

    - A detached HEAD (fix round 1) first gets a branch, `bakeoff/aside-<label>-<UTC timestamp>`, at that HEAD, so
      commits reachable only from it stay reachable after `main` is checked out.
    - A dirty tree has its changes stashed (untracked files included, ignored ones such as `.venv` kept) under
      `message` — kept in the repo, never deleted.
    - Any other branch, or the detached HEAD, is left for `main`.

    Nothing the arm made is deleted: its commits stay on their branch (or the aside branch), its edits in the stash."""
    st = state(p)
    rec = {"branch": st.branch, "dirty": st.dirty, "stashed": False, "checked_out_main": False, "aside_branch": None}
    if not st.branch:                                             # detached HEAD
        name = f"bakeoff/aside-{label}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        git(p, "branch", name, "HEAD", write=True)
        rec["aside_branch"] = name
    if st.dirty:
        git(p, "stash", "push", "--include-untracked", "-m", message, write=True, env=_who_env(IDENTITY))
        rec["stashed"] = True
    if st.branch != "main":
        git(p, "checkout", "-q", "main", write=True)
        rec["checked_out_main"] = True
    return rec


def checkout_paths(p: Paths, paths_: list[str]) -> None:
    if paths_:
        git(p, "checkout", "--", *paths_, write=True)


def remove_untracked(p: Paths, paths_: list[str], dirs: bool = False) -> None:
    """`dirs=True` (`clean -ffd`) also removes untracked directories, nested repositories included."""
    if paths_:
        git(p, "clean", "-ffd" if dirs else "-f", "-q", "--", *paths_, write=True)


def remove_ignored(p: Paths, paths_: list[str]) -> None:
    """Remove these ignored paths (`clean -ffdX`: only what .gitignore ignores, directories included)."""
    if paths_:
        git(p, "clean", "-ffdX", "-q", "--", *paths_, write=True)


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


def staged_blobs() -> list[tuple[str, str, bytes]]:
    """The harness repo only (the pre-commit hook's `runner scan --staged`, fix round 1): (path, mode, content)
    of every staged, non-deleted path, read from the INDEX (`ls-files -s` + `cat-file --batch`), so a secret
    that is staged but no longer in the working copy is still what gets scanned. Mode 120000 is link text."""
    root = str(REPO_ROOT)
    names = {os.fsdecode(n) for n in subprocess.run(
        ["git", "-C", root, "diff", "--cached", "--name-only", "-z", "--diff-filter=d"],
        capture_output=True, check=True).stdout.split(b"\0") if n}
    entries = []
    for rec in subprocess.run(["git", "-C", root, "ls-files", "-s", "-z"], capture_output=True,
                              check=True).stdout.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, sha, _stage = meta.decode().split(" ")
        if os.fsdecode(path) in names and mode != "160000":           # a gitlink has no blob here
            entries.append((os.fsdecode(path), mode, sha))
    if not entries:
        return []
    out = subprocess.run(["git", "-C", root, "cat-file", "--batch"], capture_output=True, check=True,
                         input="".join(f"{sha}\n" for _, _, sha in entries).encode()).stdout
    blobs, i = [], 0
    for path, mode, sha in entries:
        nl = out.index(b"\n", i)
        head = out[i:nl].split(b" ")
        if len(head) != 3 or head[0].decode() != sha:
            raise RuntimeError(f"git cat-file --batch: unexpected header for {path}")
        size = int(head[2])
        blobs.append((path, mode, out[nl + 1:nl + 1 + size]))
        i = nl + 1 + size + 1
    return blobs


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
