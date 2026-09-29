"""Secret scan of evidence, results, snapshots and everything `publish` pushes (design §7; review S-2, Task 21).

Transcripts, streams and egress logs are committed and eventually published, and arm repos are pushed public
after the bake-off. An arm that runs `gh auth token`, `cat ~/.config/gh/hosts.yml` or `env` puts its PAT into a
transcript. So evidence is scanned for token SHAPES (`PATTERNS`) and for the actual VALUES (`literals()`: the
keychain OAuth token via `Credential.raw_for_scanner` — this module is its only caller, enforced by a test — the
dry-run dummy token, and every arm home's PAT file values). `.gz` is decompressed (multi-member, capped).

A finding is reported by path, line and kind only, never the matched text; a path or name that itself holds a
secret is shown with that part `<redacted>`. `require_clean` turns findings into a `SecretFound` harness fault
(`secret-in-evidence`, `secret-in-publish`) whose signature is the first finding's kind.

Hostile input: arm trees (and so evidence and snapshots) are arm-written. The walk reuses
`transcripts.safe_files` (never follows a link); files are read with `transcripts.open_regular` (O_NOFOLLOW |
O_NONBLOCK, fstat regular-file check, a size cap). A symlink is never followed: its TARGET TEXT is scanned (git
publishes a link as that text). A FIFO or socket has no content and is passed over; anything that should hold
content but cannot be read (an unlistable directory, a corrupt or over-cap `.gz`, a file over SCAN_MAX_BYTES, a
failed history export) is an `unscannable` finding: the scan fails closed.

What is scanned where (orchestration decides WHEN; preflight row 36, m12):
  * `scan_tree(dir)`       — any evidence dir: `results/<pass>/<arm>/NN`, `00-setup` (shell-history.txt, setup
                             transcripts), a whole results tree. `runner scan PATH…`.
  * `scan_snapshot(p, tar)`— a `snapshots/*.tar`, extracted in a container, plus the `git fast-export` history of
                             every git dir in it (work repo and the bare origin). The arm-home PAT files
                             (`home/.config/gh/hosts.yml`, `home/.bk-mcp.json`) are exempt for the PAT itself
                             (they hold it by design, OD16) but not for any other secret.
  * `scan_arm(p, lits)`    — results + every snapshot of one arm. `runner scan --arm PASS ARM`.
  * `scan_publish(tree, history)` — what `repo.publish` pushes: the tip tree AND the full history.
  * `scan_files(paths)`    — the pre-commit hook (`runner scan --staged`).
RESIDUAL: git objects that no ref or reflog reaches are not in a snapshot's history scan (they are never
pushed); pack deltas in the raw snapshot files are only scanned through that history export.
"""
from __future__ import annotations

import os, re, stat, uuid, zlib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from runner import faults, paths, transcripts

PATTERNS: dict[str, re.Pattern[bytes]] = {
    "github-pat": re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    "github-token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "anthropic-token": re.compile(rb"sk-ant-[A-Za-z0-9_\-]{30,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"),
}
GITHUB_KINDS = frozenset({"github-pat", "github-token"})
LITERAL, UNSCANNABLE = "literal", "unscannable"
DRY_RUN_TOKEN = "dry-run-dummy-token"          # credentials.dummy()'s value
CHUNK_BYTES = 1 << 20
OVERLAP = 4096                                  # bytes carried between chunks (>= any detectable prefix)
SCAN_MAX_BYTES = 16 << 30                       # per file, and per decompressed .gz
MIN_LITERAL = 8                                 # shorter literals would match everywhere
MIN_HOME_NEEDLE = 20                            # an arm-written PAT file cannot make every file match
MAX_HITS_PER_FILE = 1000
MAX_HISTORY_LINE = 1 << 20                      # a fast-export command line (paths, identities)
PAT_FILES = (".config/gh/hosts.yml", ".bk-mcp.json")   # relative to an arm home (checklist._install_github_pat)
REDACTED = "<redacted>"
FAKE_MARK = b"secret-scan: fake"                # harness sources only: a test's fake token (see scan_files)


@dataclass(frozen=True)
class Finding:
    path: str          # where; any secret inside the name itself is <redacted>
    kind: str          # a PATTERNS key, "literal" or "unscannable"
    line: int          # 1-based line in the (decompressed) content; 0 = the name / a header / whole file


class SecretFound(faults.HarnessFault):
    """`secret-in-evidence` (a step's evidence, setup, snapshots) or `secret-in-publish`. Names every place
    (up to a limit), never the secret."""

    def __init__(self, fault: str, findings: Iterable[Finding]):
        self.findings = list(findings)
        super().__init__(fault, self.findings[0].kind if self.findings else "none", describe(self.findings))


def describe(findings: Iterable[Finding], limit: int = 20) -> str:
    fs = list(findings)
    out = "; ".join(f"{f.path}:{f.line} {f.kind}" for f in fs[:limit])
    return out + (f"; … {len(fs) - limit} more" if len(fs) > limit else "")


def require_clean(findings: Iterable[Finding], fault: str = "secret-in-evidence") -> None:
    fs = list(findings)
    if fs:
        raise SecretFound(fault, fs)


# ---- the matcher ------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Rules:
    needles: tuple[bytes, ...]
    skip_kinds: frozenset[str] = frozenset()
    skip_needles: frozenset[bytes] = frozenset()
    fake_ok: bool = False           # a PATTERN hit on a line carrying FAKE_MARK is not a finding (never a literal)

    def exempt(self, needles: Iterable[bytes]) -> "_Rules":
        """For an arm-home PAT file: the PAT (its shape and its value) is there by design; nothing else is."""
        return _Rules(self.needles, GITHUB_KINDS, frozenset(needles))

    def harness_source(self) -> "_Rules":
        """A harness source file outside results/: marked fake test tokens pass; the dry-run dummy value (which
        the runner's own source and tests must contain) is not a needle. Every real value still is."""
        return _Rules(tuple(n for n in self.needles if n != DRY_RUN_TOKEN.encode()), self.skip_kinds,
                      self.skip_needles, True)


def _rules(literals: Iterable[str]) -> _Rules:
    seen: dict[bytes, None] = {}
    for lit in literals:
        if lit and len(lit) >= MIN_LITERAL:
            seen[lit.encode()] = None
    return _Rules(tuple(seen))


def _search(buf: bytes, line0: int, rules: _Rules, hits: set[tuple[str, int]]) -> None:
    for kind, rx in PATTERNS.items():
        if kind in rules.skip_kinds:
            continue
        for m in rx.finditer(buf):
            if rules.fake_ok:
                end = buf.find(b"\n", m.end())
                if FAKE_MARK in buf[buf.rfind(b"\n", 0, m.start()) + 1:end if end != -1 else len(buf)]:
                    continue
            hits.add((kind, line0 + buf.count(b"\n", 0, m.start())))
            if len(hits) >= MAX_HITS_PER_FILE:
                return
    for n in rules.needles:
        if n in rules.skip_needles:
            continue
        i = buf.find(n)
        while i != -1 and len(hits) < MAX_HITS_PER_FILE:
            hits.add((LITERAL, line0 + buf.count(b"\n", 0, i)))
            i = buf.find(n, i + 1)


def _scan_chunks(chunks: Iterable[bytes], rules: _Rules) -> set[tuple[str, int]]:
    """(kind, line) hits over a byte stream read in pieces. OVERLAP bytes (at least the longest needle) are
    carried into the next search, so a token split across pieces is found at its true line."""
    hits: set[tuple[str, int]] = set()
    keep = max([OVERLAP, *(len(n) for n in rules.needles)])
    buf, line0 = b"", 1
    for chunk in chunks:
        if not chunk:
            continue
        buf += chunk
        _search(buf, line0, rules, hits)
        if len(hits) >= MAX_HITS_PER_FILE:
            break
        if len(buf) > keep:
            cut = len(buf) - keep
            line0 += buf.count(b"\n", 0, cut)
            buf = buf[cut:]
    return hits


def _redact(name: str, rules: _Rules) -> str:
    b = name.encode(errors="surrogateescape")
    for rx in PATTERNS.values():
        b = rx.sub(REDACTED.encode(), b)
    for n in rules.needles:
        b = b.replace(n, REDACTED.encode())
    return b.decode(errors="replace")


def _findings(where: str, hits: Iterable[tuple[str, int]], rules: _Rules) -> list[Finding]:
    shown = _redact(where, rules)
    return [Finding(shown, k, n) for k, n in sorted(hits, key=lambda h: (h[1], h[0]))]


# ---- readers ------------------------------------------------------------------------------------------------
class _Unscannable(Exception):
    pass


def _gunzip(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """Decompressed pieces of a (multi-member) gzip stream, capped at SCAN_MAX_BYTES; raises _Unscannable on a
    corrupt or truncated stream or past the cap (a gzip bomb)."""
    d, total, started = zlib.decompressobj(wbits=31), 0, False
    for chunk in chunks:
        while chunk:
            started = True
            try:
                out = d.decompress(chunk, CHUNK_BYTES)
                while True:
                    total += len(out)
                    if total > SCAN_MAX_BYTES:
                        raise _Unscannable("gzip over the cap")
                    if out:
                        yield out
                    if not d.unconsumed_tail:
                        break
                    out = d.decompress(d.unconsumed_tail, CHUNK_BYTES)
            except zlib.error as e:
                raise _Unscannable(f"gzip: {e}") from None
            if d.eof:
                chunk = d.unused_data
                d = zlib.decompressobj(wbits=31)
                if not chunk.strip(b"\0"):
                    chunk = b""
                    started = False
            else:
                chunk = b""
    if started and not d.eof:
        raise _Unscannable("gzip truncated")


def _scan_file(p: Path, real_root: str, where: str, rules: _Rules) -> list[Finding]:
    got = transcripts.open_regular(p, real_root, max_bytes=SCAN_MAX_BYTES, allow_hardlinked=True)
    if isinstance(got, str):
        if got == "not-regular":                          # swapped for a FIFO/socket: no content to hold a secret
            return []
        return [Finding(_redact(where, rules), UNSCANNABLE, 0)]
    try:
        raw = transcripts.read_chunks(got, SCAN_MAX_BYTES)
        hits = _scan_chunks(_gunzip(raw) if p.name.endswith(".gz") else raw, rules)
    except (_Unscannable, transcripts.Oversize, OSError):
        return [Finding(_redact(where, rules), UNSCANNABLE, 0)]
    finally:
        os.close(got)
    return _findings(where, hits, rules)


def _scan_link(p: Path, where: str, rules: _Rules) -> list[Finding]:
    try:
        target = os.fsencode(os.readlink(p))
    except OSError:
        return [Finding(_redact(where, rules), UNSCANNABLE, 0)]
    return _findings(where, _scan_chunks([target], rules), rules)


def _walk(root: Path, rules: _Rules, *, exempt: Mapping[str, _Rules] | None = None,
          show=lambda rel, full: str(full)) -> list[Finding]:
    """Every entry under `root`, never following a link: names, regular files (hard-linked too), link texts."""
    exempt = exempt or {}
    skipped: list[dict] = []
    files = transcripts.safe_files(root, "*", skipped=skipped)
    real_root = os.path.realpath(root)
    out: list[Finding] = []

    def rel_of(p: Path) -> str:
        return os.path.relpath(p, root)

    for f in files:
        rel = rel_of(f)
        out += _scan_file(f, real_root, show(rel, f), exempt.get(rel, rules))
    for e in skipped:
        rel, reason = e["path"], e["reason"]
        full = root / rel if rel != "." else root
        where = show(rel, full)
        if reason == "symlink":
            out += _scan_link(full, where, rules)
        elif reason in ("hardlinked", "oversize"):
            out += _scan_file(full, real_root, where, exempt.get(rel, rules))
        elif reason == "not-regular":
            try:
                st = os.lstat(full)
            except OSError:
                out.append(Finding(_redact(where, rules), UNSCANNABLE, 0))
                continue
            if not (stat.S_ISFIFO(st.st_mode) or stat.S_ISSOCK(st.st_mode)):
                out.append(Finding(_redact(where, rules), UNSCANNABLE, 0))
        else:                                             # unreadable, outside-root: content unknown
            out.append(Finding(_redact(where, rules), UNSCANNABLE, 0))
    # every name in the tree (a secret can be a file or directory name)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in (*dirnames, *filenames):
            full = Path(dirpath) / name
            hits = _scan_chunks([os.fsencode(name)], rules)
            out += [Finding(_redact(show(rel_of(full), full), rules), k, 0) for k, _ in sorted(hits)]
    return sorted(set(out), key=lambda f: (f.path, f.line, f.kind))


# ---- public scans -------------------------------------------------------------------------------------------
def scan_tree(root: Path, literals: Iterable[str] = ()) -> list[Finding]:
    """Every file under `root` (a link's target text, never its target; `.gz` decompressed)."""
    root = Path(root)
    rules = _rules(literals)
    if os.path.islink(root):
        return _scan_link(root, str(root), rules)
    if not root.is_dir():
        return scan_files([root], literals) if os.path.lexists(root) else []
    return _walk(root, rules)


def _in_results(p: Path) -> bool:
    try:
        Path(os.path.abspath(p)).relative_to(os.path.abspath(paths.RESULTS))
        return True
    except ValueError:
        return False


def scan_files(paths_: Iterable[Path], literals: Iterable[str] = (), *, harness: bool = False) -> list[Finding]:
    """Exactly these files. A link is scanned as its target text; a missing path is skipped (a staged deletion).
    `harness=True` is the pre-commit hook over the harness repo: files OUTSIDE results/ are sources, where a
    token-shaped test fixture may be marked `secret-scan: fake` on its line and the dry-run dummy value is not a
    needle (`_Rules.harness_source`). Files under results/ are evidence and get the full rules."""
    base = _rules(literals)
    out: list[Finding] = []
    for p in paths_:
        p = Path(p)
        rules = base.harness_source() if harness and not _in_results(p) else base
        if os.path.islink(p):
            out += _scan_link(p, str(p), rules)
        elif p.is_dir():
            out += _walk(p, rules)
        elif os.path.lexists(p):
            out += _scan_file(p, os.path.realpath(p.parent), str(p), rules)
            out += [Finding(_redact(str(p), rules), k, 0) for k, _ in sorted(_scan_chunks([os.fsencode(p.name)], rules))]
    return out


def _read_exact(fh, n: int) -> Iterator[bytes]:
    while n > 0:
        b = fh.read(min(n, CHUNK_BYTES))
        if not b:
            raise _Unscannable("fast-export stream ends inside a data block")
        n -= len(b)
        yield b


def scan_history(export: Path | None, label: str, literals: Iterable[str] = ()) -> list[Finding]:
    """A `git fast-export --show-original-ids` stream (gitops.fast_export): every blob, commit and tag message,
    identity, file name and link target reachable from what was exported. Data blocks are read by their
    declared length, so content can never be mistaken for a command. A finding names the object —
    `<label>: blob <oid> (<first path>)`, `<label>: commit <oid> message`, `<label>: commit <oid>` (a header
    line: identity or path) — never the text. A missing or malformed stream is `unscannable`."""
    rules = _rules(literals)
    if export is None:
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]
    got = transcripts.open_regular(Path(export), os.path.realpath(Path(export).parent), max_bytes=1 << 62)
    if isinstance(got, str):
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]
    objs: list[dict] = []
    mark_obj: dict[bytes, dict] = {}
    pending: list[tuple[dict | None, str, str, int]] = []
    cur: dict | None = None
    try:
        with os.fdopen(got, "rb", buffering=CHUNK_BYTES) as fh:
            while line := fh.readline(MAX_HISTORY_LINE + 1):
                if len(line) > MAX_HISTORY_LINE:
                    raise _Unscannable("fast-export line over the cap")
                s = line.rstrip(b"\n")
                if not s:
                    continue
                word = s.split(b" ", 1)[0]
                if word in (b"blob", b"commit", b"tag", b"reset"):
                    cur = {"type": word.decode(), "oid": None, "path": None}
                    objs.append(cur)
                elif word == b"mark" and cur is not None:
                    mark_obj[s[5:]] = cur
                elif word == b"original-oid" and cur is not None:
                    cur["oid"] = s[13:].decode(errors="replace")
                elif word == b"data":
                    n = s[5:]
                    if not n.isdigit():
                        raise _Unscannable("fast-export data without a length")
                    for kind, ln in _scan_chunks(_read_exact(fh, int(n)), rules):
                        pending.append((cur, "data", kind, ln))
                    continue
                elif word == b"M":
                    parts = s.split(b" ", 3)
                    if len(parts) == 4 and parts[2] in mark_obj and mark_obj[parts[2]]["path"] is None:
                        mark_obj[parts[2]]["path"] = parts[3].decode(errors="replace")
                for kind, _ in _scan_chunks([s], rules):
                    pending.append((cur, "header", kind, 0))
    except (_Unscannable, OSError):
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]

    def name(obj: dict | None, part: str) -> str:
        if obj is None:
            return f"{label}: history"
        oid = obj["oid"] or "?"
        if obj["type"] == "blob":
            return f"{label}: blob {oid} ({obj['path'] or '?'})"
        return f"{label}: {obj['type']} {oid}" + (" message" if part == "data" else "")

    return sorted({Finding(_redact(name(o, part), rules), k, ln) for o, part, k, ln in pending},
                  key=lambda f: (f.path, f.line, f.kind))


def scan_publish(tree: Path, history: Path | None, literals: Iterable[str] = ()) -> list[Finding]:
    """What `repo.publish` pushes: the tip tree and the full history of main."""
    lits = list(literals)
    return scan_tree(tree, lits) + scan_history(history, "main", lits)


def _git_dirs(root: Path) -> list[str]:
    """Git dirs under `root` (a `HEAD` file with `objects/` and `refs/` beside it), never through a link."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if not (d / n).is_symlink()]
        if "HEAD" in filenames and not (d / "HEAD").is_symlink() and \
                {"objects", "refs"} <= set(dirnames):
            out.append(os.path.relpath(d, root))
            dirnames[:] = []                             # its insides are scanned raw by the tree walk
    return sorted(out)


def scan_snapshot(p: paths.Paths, snapshot: Path, literals: Iterable[str] = ()) -> list[Finding]:
    """A `snapshots/*.tar`: extracted in a container into scratch, scanned (names `<tar>:<member>`), plus
    the full `git fast-export` history of every git dir in it; the extraction is removed afterwards. The home
    PAT files are exempt for the PAT itself only (see the module docstring)."""
    from runner import gitops, repo
    lits = list(literals)
    rules = _rules(lits)
    work = p.scratch / "secret-scan" / uuid.uuid4().hex[:12]
    tree = work / "tree"
    try:
        repo.extract_snapshot(p, snapshot, tree)
        home = tree / "home"
        pats = [v.encode() for v in home_pat_values(home)]      # this snapshot's own PAT values only
        exempt = {f"home/{rel}": rules.exempt(pats) for rel in PAT_FILES}
        found = _walk(tree, rules, exempt=exempt, show=lambda rel, full: f"{snapshot.name}:{rel}")
        dirs = _git_dirs(tree)
        if dirs:
            exports = gitops.fast_export(p, tree, dirs, work / "history")
            for d, fe in zip(dirs, exports):
                found += scan_history(fe, f"{snapshot.name}:{d} history", lits)
        return found
    finally:
        repo.remove_tree(work)
        parent = p.scratch / "secret-scan"
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def scan_arm(p: paths.Paths, literals: Iterable[str] = (), *, snapshots: bool = True) -> list[Finding]:
    """One arm: its whole results tree (every step's evidence, `00-setup` with shell-history.txt and the setup
    transcripts) and, with `snapshots`, every `snapshots/*.tar`. The arm home's PAT values are added to the
    needles."""
    lits = [*literals, *home_pat_values(p.home)]
    found = scan_tree(p.results, lits) if p.results.is_dir() else []
    if snapshots and p.snapshots.is_dir() and not p.snapshots.is_symlink():
        for snap in sorted(p.snapshots.glob("*.tar")):
            if snap.is_file() and not snap.is_symlink():
                found += scan_snapshot(p, snap, lits)
    return found


# ---- needles ------------------------------------------------------------------------------------------------
_OAUTH_TOKEN = re.compile(rb"oauth_token:\s*['\"]?([^\s'\"]+)")


def home_pat_values(home: Path) -> list[str]:
    """The PAT values in an arm home's PAT files (`hosts.yml` oauth_token, and any GitHub-shaped token in
    either file), read without following links and capped. Values shorter than MIN_HOME_NEEDLE are ignored:
    the home is arm-writable, and a one-letter "PAT" would make every file a finding."""
    out: dict[str, None] = {}
    if os.path.islink(home) or not home.is_dir():
        return []
    real = os.path.realpath(home)
    for rel in PAT_FILES:
        got = transcripts.open_regular(home / rel, real, max_bytes=1 << 20)
        if isinstance(got, str):
            continue
        try:
            data = b"".join(transcripts.read_chunks(got, 1 << 20))
        except transcripts.Oversize:
            continue
        finally:
            os.close(got)
        vals = _OAUTH_TOKEN.findall(data) + [m.group(0) for k in GITHUB_KINDS for m in PATTERNS[k].finditer(data)]
        for v in vals:
            if len(v) >= MIN_HOME_NEEDLE:
                out[v.decode(errors="replace")] = None
    return list(out)


def _arm_homes() -> Iterator[Path]:
    """`state/<pass>/<arm>/home`, never through a link."""
    state = paths.STATE
    if os.path.islink(state) or not state.is_dir():
        return
    for pass_dir in sorted(state.iterdir()):
        if pass_dir.is_symlink() or not pass_dir.is_dir():
            continue
        for arm_dir in sorted(pass_dir.iterdir()):
            home = arm_dir / "home"
            if not arm_dir.is_symlink() and arm_dir.is_dir() and home.is_dir() and not home.is_symlink():
                yield home


def literals(cred=None) -> list[str]:
    """The values to search for: the dry-run dummy token; the Claude OAuth token (`cred`, else the keychain
    — skipped if there is no usable item); and every arm home's PAT values (`home_pat_values`)."""
    from runner import credentials
    out: dict[str, None] = {DRY_RUN_TOKEN: None}
    try:
        c = cred if cred is not None else credentials.from_keychain()
    except RuntimeError:
        c = None
    if c is not None:
        out[c.raw_for_scanner()] = None
    for home in _arm_homes():
        for v in home_pat_values(home):
            out[v] = None
    return list(out)


def credential_files(config_dir: Path | None, cred, since: float) -> list[str]:
    """Files under config_dir changed during the turn that contain the token, and any .credentials.json (S-3;
    moved here from runner.session so that only this module reads the raw token). Never follows a link and
    never blocks: the transcripts no-follow readers. A `.credentials.json` of any file type is reported by name
    without being read."""
    if config_dir is None or os.path.islink(config_dir) or not config_dir.is_dir():
        return []
    needle, hits = cred.raw_for_scanner().encode(), set()
    for root, _dirs, files in os.walk(config_dir, followlinks=False):
        if ".credentials.json" in files:
            hits.add(str((Path(root) / ".credentials.json").relative_to(config_dir)))
    real_root = os.path.realpath(config_dir)
    for f in transcripts.safe_files(config_dir, "*"):
        if transcripts.safe_contains(f, real_root, needle, since=since):
            hits.add(str(f.relative_to(config_dir)))
    return sorted(hits)
