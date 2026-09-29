"""Secret scan of evidence, results, snapshots and everything `publish` pushes (design §7; review S-2, Task 21).

Transcripts, streams and egress logs are committed and eventually published, and arm repos are pushed public
after the bake-off. An arm that runs `gh auth token`, `cat ~/.config/gh/hosts.yml` or `env` puts its PAT into a
transcript. So evidence is scanned for token SHAPES (`PATTERNS`) and for the actual VALUES (`literals()`: the
keychain OAuth token via `Credential.raw_for_scanner` — this module is its only caller, enforced by a test — the
keychain PAT items `bakeoff-gh-<pass>-<arm>`, every arm home's PAT file values, and the dry-run dummy token).

Every known value is also searched ENCODED (fix round 1): base64 (standard and URL-safe) at all three byte
alignments, so `Basic base64("x-access-token:<v>")` or any other prefix is covered, with the edge characters
that depend on neighbouring bytes trimmed; and hex (lower and upper case). Every value and encoding is also
searched in a copy of the text with CR and LF removed, so a terminal-wrapped or MIME-wrapped token is found (at
the line where it starts).

Content is classified by MAGIC BYTES, not by name: gzip is decompressed (multi-member, capped), zip is read in
memory (capped; members named `<file>!<member>`, never extracted to disk), and xz / bzip2 / zstd are
`unscannable` findings. Nesting is followed to MAX_DEPTH.

A finding is reported by path, line and kind only, never the matched text; a path or name that itself holds a
secret is shown with that part `<redacted>`. `require_clean` turns findings into a `SecretFound` harness fault
(`secret-in-evidence`, `secret-in-publish`) whose signature is the first finding's kind.

Hostile input: arm trees (and so evidence and snapshots) are arm-written. The walk reuses
`transcripts.safe_files` (never follows a link); files are read with `transcripts.open_regular` (O_NOFOLLOW |
O_NONBLOCK, fstat regular-file check, a size cap). A symlink is never followed: its TARGET TEXT is scanned (git
publishes a link as that text). A FIFO or socket has no content and is passed over; anything that should hold
content but cannot be read (an unlistable directory, a corrupt or over-cap archive, a file over SCAN_MAX_BYTES,
a failed history export) is an `unscannable` finding: the scan fails closed.

What is scanned where (orchestration decides WHEN; preflight row 36, m12):
  * `scan_tree(dir)`       — any evidence dir: `results/<pass>/<arm>/NN`, `00-setup` (shell-history.txt, setup
                             transcripts), a whole results tree. `runner scan PATH…`.
  * `scan_snapshot(p, tar, pat=)` — a `snapshots/*.tar`, extracted in a container, plus the `git fast-export`
                             history of every git dir in it (work repo and the bare origin). In the arm-home PAT
                             files (`home/.config/gh/hosts.yml`, `home/.bk-mcp.json`) only the arm's keychain PAT
                             (`pat`) is exempt — they hold it by design (OD16); any other token there is a finding.
  * `scan_arm(p, lits)`    — results + every snapshot of one arm. `runner scan --arm PASS ARM`.
  * `scan_publish(tree, history)` — what `repo.publish` pushes: the tip tree AND the full history.
  * `scan_blobs(items, harness=True)` — the pre-commit hook (`runner scan --staged`): the INDEX blobs.
The `secret-scan: fake` line mark is honoured only by the pre-commit scan, only in files under `tests/`, only
for a PATTERN hit whose token is recognisably fake (says FAKE, or is a run of very few distinct characters) or
whose line is in FAKE_FIXTURE_LINES — never for a known value, never under results/, never in any other scan.
RESIDUAL: git objects that no ref or reflog reaches are not in a snapshot's history scan (they are never
pushed); pack deltas in the raw snapshot files are only scanned through that history export.
"""
from __future__ import annotations

import base64, hashlib, io, itertools, os, re, stat, uuid, zipfile, zlib
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
SCAN_MAX_BYTES = 16 << 30                       # per file, per decompressed stream, per zip member
ZIP_MAX_BYTES = 256 << 20                       # a zip is read into memory: capped
MAX_DEPTH = 3                                   # nested archives
MIN_LITERAL = 8                                 # shorter literals would match everywhere
MIN_HOME_NEEDLE = 20                            # an arm-written PAT file cannot make every file match
MAX_HITS_PER_FILE = 1000
MAX_HISTORY_LINE = 1 << 20                      # a fast-export command line (paths, identities)
PAT_FILES = (".config/gh/hosts.yml", ".bk-mcp.json")   # relative to an arm home (checklist._install_github_pat)
PAT_PASSES = ("pass1", "pass2", "canary")      # passes with a GitHub repo, so a keychain PAT item (OD16)
REDACTED = "<redacted>"
FAKE_MARK = b"secret-scan: fake"                # pre-commit, tests/ only (see module docstring)
# Explicit allowlist of token-shaped fixture lines that are fake but do not say so: (repo-relative path,
# sha256 hex of the line without its newline). Empty: every fixture in the repo today says FAKE.
FAKE_FIXTURE_LINES: frozenset[tuple[str, str]] = frozenset()

_GZIP = b"\x1f\x8b"
_ZIP = (b"PK\x03\x04", b"PK\x05\x06")
_OTHER = {"xz": re.compile(rb"\A\xfd7zXZ\x00"), "bzip2": re.compile(rb"\ABZh[1-9](?:1AY&SY|\x17rE8P\x90)"),
          "zstd": re.compile(rb"\A\x28\xb5\x2f\xfd")}
_NL = re.compile(rb"[\r\n]")


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


# ---- needles --------------------------------------------------------------------------------------------------
def _b64_cores(v: bytes) -> list[bytes]:
    """The base64 characters that depend ONLY on `v`, for each of the 3 alignments `v` can have after any
    prefix; the first characters (mixed with the prefix) and the last (mixed with what follows) are trimmed."""
    out = []
    for i, start in ((0, 0), (1, 2), (2, 3)):
        enc = base64.b64encode(b"\0" * i + v).rstrip(b"=")
        end = len(enc) if (i + len(v)) % 3 == 0 else len(enc) - 1
        core = enc[start:end]
        out += [core, core.replace(b"+", b"-").replace(b"/", b"_")]
    return out


def _derived(v: bytes) -> list[bytes]:
    """A known value and its encodings (fix round 1): itself, base64 (standard, URL-safe; every alignment), hex."""
    return [v, *_b64_cores(v), v.hex().encode(), v.hex().upper().encode()]


@dataclass(frozen=True)
class _Rules:
    needles: tuple[tuple[bytes, bytes], ...]          # (searched bytes, the value it derives from)
    exempt_values: frozenset[bytes] = frozenset()     # PAT-file exemption: this value's shape and encodings
    fake_ok: bool = False                             # pre-commit, tests/: a marked recognisably-fake pattern hit
    source_path: str = ""                             # repo-relative path, for FAKE_FIXTURE_LINES

    def exempt(self, values: Iterable[bytes]) -> "_Rules":
        return _Rules(self.needles, frozenset(v for v in values if v), self.fake_ok, self.source_path)

    def harness_source(self, rel: str, tests: bool) -> "_Rules":
        """A harness source file outside results/: the dry-run dummy value (which the runner's own source and
        tests must contain) is not a needle; under tests/ a marked fake fixture may pass. Every other value
        stays a needle."""
        dummy = DRY_RUN_TOKEN.encode()
        return _Rules(tuple(n for n in self.needles if n[1] != dummy), self.exempt_values, tests, rel)

    @property
    def longest(self) -> int:
        return max((len(n) for n, _ in self.needles), default=0)


def _rules(literals: Iterable[str]) -> _Rules:
    seen: dict[tuple[bytes, bytes], None] = {}
    for lit in literals:
        if lit and len(lit) >= MIN_LITERAL:
            v = lit.encode()
            for d in _derived(v):
                if len(d) >= MIN_LITERAL:
                    seen[(d, v)] = None
    return _Rules(tuple(seen))


def _looks_fake(token: bytes) -> bool:
    body = re.sub(rb"^(?:github_pat_|gh[pousr]_|sk-ant-(?:[a-z]+\d*-)?)", b"", token)
    return b"FAKE" in body.upper() or len(set(body.replace(b"_", b"").replace(b"-", b""))) <= 4


def _line_at(buf: bytes, start: int, end: int) -> bytes:
    a = buf.rfind(b"\n", 0, start) + 1
    b = buf.find(b"\n", end)
    return buf[a:b if b != -1 else len(buf)].rstrip(b"\r")


def _fake_ok(buf: bytes, m: re.Match, rules: _Rules) -> bool:
    line = _line_at(buf, m.start(), m.end())
    if FAKE_MARK not in line:
        return False
    return _looks_fake(m.group(0)) or \
        (rules.source_path, hashlib.sha256(line).hexdigest()) in FAKE_FIXTURE_LINES


def _search(buf: bytes, line0: int, rules: _Rules, hits: set[tuple[str, int]]) -> None:
    def line_of(i: int) -> int:
        return line0 + buf.count(b"\n", 0, i)

    for kind, rx in PATTERNS.items():
        for m in rx.finditer(buf):
            if rules.exempt_values and kind in GITHUB_KINDS and any(m.group(0) in v for v in rules.exempt_values):
                continue
            if rules.fake_ok and _fake_ok(buf, m, rules):
                continue
            hits.add((kind, line_of(m.start())))
            if len(hits) >= MAX_HITS_PER_FILE:
                return
    needles = [n for n, origin in rules.needles if origin not in rules.exempt_values]
    if not needles:
        return
    for n in needles:
        i = buf.find(n)
        while i != -1 and len(hits) < MAX_HITS_PER_FILE:
            hits.add((LITERAL, line_of(i)))
            i = buf.find(n, i + 1)
    # terminal/MIME wrapping: the same needles in a copy without CR/LF, mapped back to the raw start
    if b"\n" not in buf and b"\r" not in buf:
        return
    flat, removed = buf.translate(None, b"\r\n"), None
    for n in needles:
        j = flat.find(n)
        while j != -1 and len(hits) < MAX_HITS_PER_FILE:
            if removed is None:
                removed = [m.start() for m in _NL.finditer(buf)]
            r = j
            for p in removed:
                if p <= r:
                    r += 1
                else:
                    break
            hits.add((LITERAL, line_of(r)))
            j = flat.find(n, j + 1)


def _scan_chunks(chunks: Iterable[bytes], rules: _Rules) -> set[tuple[str, int]]:
    """(kind, line) hits over a byte stream read in pieces. Enough bytes are carried into the next search (at
    least OVERLAP and twice the longest needle, room for wrapping) that a token split across pieces is found
    at its true line."""
    hits: set[tuple[str, int]] = set()
    keep = max(OVERLAP, 2 * rules.longest + 64)
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
    for n, _ in sorted(rules.needles, key=lambda x: -len(x[0])):
        b = b.replace(n, REDACTED.encode())
    return b.decode(errors="replace")


# ---- content (magic bytes) --------------------------------------------------------------------------------------
class _Unscannable(Exception):
    pass


Hit = tuple[str, str, int]      # (member suffix, kind, line)


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


def _capped(chunks: Iterable[bytes], cap: int) -> Iterator[bytes]:
    total = 0
    for c in chunks:
        total += len(c)
        if total > cap:
            raise _Unscannable("over the cap")
        yield c


def _zip_hits(stream: Iterable[bytes], rules: _Rules, depth: int) -> list[Hit]:
    """A zip read into memory (ZIP_MAX_BYTES), never extracted: every member name and every member's content."""
    data = b"".join(_capped(stream, ZIP_MAX_BYTES))
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError, RuntimeError):
        return [("", UNSCANNABLE, 0)]
    out: list[Hit] = []
    for info in infos:
        suffix = f"!{info.filename}"
        out += [(suffix, k, 0) for k, _ in _scan_chunks([os.fsencode(info.filename)], rules)]
        if info.is_dir():
            continue
        if info.flag_bits & 0x1 or info.file_size > SCAN_MAX_BYTES:
            out.append((suffix, UNSCANNABLE, 0))
            continue
        try:
            with zf.open(info) as fh:
                member = iter(lambda: fh.read(CHUNK_BYTES), b"")
                out += [(suffix + s, k, n) for s, k, n in _content_hits(_capped(member, SCAN_MAX_BYTES), rules, depth + 1)]
        except (_Unscannable, zipfile.BadZipFile, zlib.error, OSError, ValueError, NotImplementedError,
                RuntimeError, EOFError):
            out.append((suffix, UNSCANNABLE, 0))
    return out


def _content_hits(chunks: Iterable[bytes], rules: _Rules, depth: int = 0) -> list[Hit]:
    """Hits in a byte stream, classified by its first bytes: gzip (decompressed), zip (in memory), xz / bzip2 /
    zstd (unscannable), else plain. Oversize (transcripts.Oversize) propagates to the caller."""
    it = iter(chunks)
    head = b""
    while len(head) < 16:
        nxt = next(it, None)
        if nxt is None:
            break
        head += nxt
    stream = itertools.chain([head], it)
    if depth > MAX_DEPTH and (head.startswith(_GZIP) or head.startswith(_ZIP)):
        return [("", UNSCANNABLE, 0)]
    try:
        if head.startswith(_GZIP):
            return _content_hits(_gunzip(stream), rules, depth + 1)
        if head.startswith(_ZIP):
            return _zip_hits(stream, rules, depth)
        if any(rx.match(head) for rx in _OTHER.values()):
            return [("", UNSCANNABLE, 0)]
        return [("", k, n) for k, n in _scan_chunks(stream, rules)]
    except _Unscannable:
        return [("", UNSCANNABLE, 0)]


def _findings(where: str, hits: Iterable[Hit], rules: _Rules) -> list[Finding]:
    return sorted({Finding(_redact(where + s, rules), k, n) for s, k, n in hits},
                  key=lambda f: (f.path, f.line, f.kind))


def _name_hits(name: str, rules: _Rules) -> list[Hit]:
    return [("", k, 0) for k, _ in _scan_chunks([os.fsencode(name)], rules)]


# ---- readers ------------------------------------------------------------------------------------------------
def _scan_file(p: Path, real_root: str, where: str, rules: _Rules) -> list[Finding]:
    got = transcripts.open_regular(p, real_root, max_bytes=SCAN_MAX_BYTES, allow_hardlinked=True)
    if isinstance(got, str):
        if got == "not-regular":                          # swapped for a FIFO/socket: no content to hold a secret
            return []
        return [Finding(_redact(where, rules), UNSCANNABLE, 0)]
    try:
        hits = _content_hits(transcripts.read_chunks(got, SCAN_MAX_BYTES), rules)
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
    return _findings(where, [("", k, n) for k, n in _scan_chunks([target], rules)], rules)


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
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):   # every name (a secret can be a name)
        for name in (*dirnames, *filenames):
            full = Path(dirpath) / name
            out += _findings(show(rel_of(full), full), _name_hits(name, rules), rules)
    return sorted(set(out), key=lambda f: (f.path, f.line, f.kind))


# ---- public scans -------------------------------------------------------------------------------------------
def scan_tree(root: Path, literals: Iterable[str] = ()) -> list[Finding]:
    """Every file under `root` (a link's target text, never its target; archives by magic bytes)."""
    root = Path(root)
    rules = _rules(literals)
    if os.path.islink(root):
        return _scan_link(root, str(root), rules)
    if not root.is_dir():
        return scan_files([root], literals) if os.path.lexists(root) else []
    return _walk(root, rules)


def scan_files(paths_: Iterable[Path], literals: Iterable[str] = ()) -> list[Finding]:
    """Exactly these files. A link is scanned as its target text; a missing path is skipped."""
    rules = _rules(literals)
    out: list[Finding] = []
    for p in paths_:
        p = Path(p)
        if os.path.islink(p):
            out += _scan_link(p, str(p), rules)
        elif p.is_dir():
            out += _walk(p, rules)
        elif os.path.lexists(p):
            out += _scan_file(p, os.path.realpath(p.parent), str(p), rules)
            out += _findings(str(p), _name_hits(p.name, rules), rules)
    return out


def _in_results(rel: str) -> bool:
    from runner import gitops
    try:
        (Path(os.path.abspath(gitops.REPO_ROOT)) / rel).relative_to(os.path.abspath(paths.RESULTS))
        return True
    except ValueError:
        return False


def scan_blobs(items: Iterable[tuple[str, str, bytes]], literals: Iterable[str] = (), *,
               harness: bool = False) -> list[Finding]:
    """(repo-relative path, git mode, content) — the pre-commit hook passes `gitops.staged_blobs()`, i.e. the
    INDEX, not the working tree. Mode 120000 content is link text. With `harness=True`, a path outside results/
    is a harness source (`_Rules.harness_source`: no dummy needle; under tests/ the fake mark may apply); a path
    under results/ is evidence and gets the full rules."""
    base = _rules(literals)
    out: list[Finding] = []
    for rel, mode, data in items:
        rules = base
        if harness and not _in_results(rel):
            rules = base.harness_source(rel, tests=rel.startswith("tests/"))
        if mode == "120000":
            hits = [("", k, n) for k, n in _scan_chunks([data], rules)]
        else:
            hits = _content_hits([data], rules)
        out += _findings(rel, hits + _name_hits(rel, rules), rules)
    return out


def _read_exact(fh, n: int) -> Iterator[bytes]:
    while n > 0:
        b = fh.read(min(n, CHUNK_BYTES))
        if not b:
            raise _Unscannable("fast-export stream ends inside a data block")
        n -= len(b)
        yield b


def scan_history(export: Path | None, label: str, literals: Iterable[str] = ()) -> list[Finding]:
    """A `git fast-export --show-original-ids` stream (gitops.fast_export): every blob (archives by magic
    bytes), commit and tag message, identity, file name and link target reachable from what was exported. Data
    blocks are read by their declared length, so content can never be mistaken for a command. A finding names
    the object — `<label>: blob <oid> (<first path>)`, `<label>: commit <oid> message`, `<label>: commit <oid>`
    (a header line: identity or path) — never the text. A missing or malformed stream is `unscannable`."""
    rules = _rules(literals)
    if export is None:
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]
    got = transcripts.open_regular(Path(export), os.path.realpath(Path(export).parent), max_bytes=1 << 62)
    if isinstance(got, str):
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]
    mark_obj: dict[bytes, dict] = {}
    pending: list[tuple[dict | None, str, str, str, int]] = []
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
                elif word == b"mark" and cur is not None:
                    mark_obj[s[5:]] = cur
                elif word == b"original-oid" and cur is not None:
                    cur["oid"] = s[13:].decode(errors="replace")
                elif word == b"data":
                    n = s[5:]
                    if not n.isdigit():
                        raise _Unscannable("fast-export data without a length")
                    body = _read_exact(fh, int(n))
                    if cur is not None and cur["type"] == "blob":
                        hits = _content_hits(body, rules)
                        for _ in body:                    # drain what detection did not read (it stops early)
                            pass
                    else:
                        hits = [("", k, ln) for k, ln in _scan_chunks(body, rules)]
                    pending += [(cur, "data", sfx, k, ln) for sfx, k, ln in hits]
                    continue
                elif word == b"M":
                    parts = s.split(b" ", 3)
                    if len(parts) == 4 and parts[2] in mark_obj and mark_obj[parts[2]]["path"] is None:
                        mark_obj[parts[2]]["path"] = parts[3].decode(errors="replace")
                for kind, _ in _scan_chunks([s], rules):
                    pending.append((cur, "header", "", kind, 0))
    except (_Unscannable, OSError):
        return [Finding(f"{label}: history", UNSCANNABLE, 0)]

    def name(obj: dict | None, part: str) -> str:
        if obj is None:
            return f"{label}: history"
        oid = obj["oid"] or "?"
        if obj["type"] == "blob":
            return f"{label}: blob {oid} ({obj['path'] or '?'})"
        return f"{label}: {obj['type']} {oid}" + (" message" if part == "data" else "")

    return sorted({Finding(_redact(name(o, part) + sfx, rules), k, ln) for o, part, sfx, k, ln in pending},
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


def scan_snapshot(p: paths.Paths, snapshot: Path, literals: Iterable[str] = (), *,
                  pat: str | None = None) -> list[Finding]:
    """A `snapshots/*.tar`: extracted in a container into scratch, scanned (names `<tar>:<member>`), plus
    the full `git fast-export` history of every git dir in it; the extraction is removed afterwards. In the home
    PAT files only `pat` — the arm's keychain PAT — is exempt (its shape and value); nothing else there is."""
    from runner import gitops, repo
    lits = list(literals)
    rules = _rules(lits)
    work = p.scratch / "secret-scan" / uuid.uuid4().hex[:12]
    tree = work / "tree"
    try:
        repo.extract_snapshot(p, snapshot, tree)
        exempt = {f"home/{rel}": rules.exempt([pat.encode()]) for rel in PAT_FILES} if pat else {}
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


# Keychain lookups, at most once per process (controller ruling): an absent item is cached as absent too.
# Values live only in this process's memory, like the Credential itself.
_KEYCHAIN: dict[tuple[str, ...], object] = {}


def clear_keychain_cache() -> None:
    _KEYCHAIN.clear()


def _oauth():
    """The keychain OAuth Credential (credentials.from_keychain), cached; raises RuntimeError if unusable."""
    from runner import credentials
    if ("oauth",) not in _KEYCHAIN:
        try:
            _KEYCHAIN[("oauth",)] = credentials.from_keychain()
        except RuntimeError as e:
            _KEYCHAIN[("oauth",)] = RuntimeError(str(e))
    got = _KEYCHAIN[("oauth",)]
    if isinstance(got, RuntimeError):
        raise RuntimeError(str(got))
    return got


def keychain_pat(pass_: str, arm: str) -> str | None:
    """The arm's keychain PAT item `bakeoff-gh-<pass>-<arm>` (credentials.github_pat), or None if absent;
    cached per process."""
    from runner import credentials
    key = ("pat", pass_, arm)
    if key not in _KEYCHAIN:
        try:
            _KEYCHAIN[key] = credentials.github_pat(pass_, arm) or None
        except RuntimeError:
            _KEYCHAIN[key] = None
    return _KEYCHAIN[key]      # type: ignore[return-value]


def scan_arm(p: paths.Paths, literals: Iterable[str] = (), *, snapshots: bool = True) -> list[Finding]:
    """One arm: its whole results tree (every step's evidence, `00-setup` with shell-history.txt and the setup
    transcripts) and, with `snapshots`, every `snapshots/*.tar`. The arm home's PAT values and its keychain PAT
    are added to the needles; the keychain PAT is the snapshot PAT-file exemption."""
    pat = keychain_pat(p.pass_, p.arm)
    lits = [*literals, *home_pat_values(p.home), *([pat] if pat else [])]
    found = scan_tree(p.results, lits) if p.results.is_dir() else []
    if snapshots and p.snapshots.is_dir() and not p.snapshots.is_symlink():
        for snap in sorted(p.snapshots.glob("*.tar")):
            if snap.is_file() and not snap.is_symlink():
                found += scan_snapshot(p, snap, lits, pat=pat)
    return found


# ---- literal values ---------------------------------------------------------------------------------------------
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


def _keychain_pats() -> list[str]:
    from runner import config
    out = []
    for arm in config.all_arms():
        a = config.load_arm(arm)
        if a.tracker != "github" or a.dry:
            continue
        for pass_ in PAT_PASSES:
            if config.github_slug(pass_, arm) and (v := keychain_pat(pass_, arm)):
                out.append(v)
    return out


def literals(cred=None, *, require_oauth: bool = False, keychain: bool = True) -> list[str]:
    """The values to search for: the dry-run dummy token; the Claude OAuth token (`cred`, else the keychain);
    every keychain PAT item of a GitHub-tracker arm; every arm home's PAT values. Keychain lookups are cached
    per process. A missing keychain OAuth token is skipped — unless `require_oauth` (publish), when it raises
    RuntimeError: publish fails closed. `keychain=False` (the pre-commit hook, controller ruling) never touches
    the keychain: `cred` if given, and the arm-home PAT values."""
    if require_oauth and not keychain:
        raise ValueError("require_oauth needs the keychain")
    out: dict[str, None] = {DRY_RUN_TOKEN: None}
    c = cred
    if c is None and keychain:
        try:
            c = _oauth()
        except RuntimeError:
            if require_oauth:
                raise
    if c is not None:
        out[c.raw_for_scanner()] = None
    for v in (_keychain_pats() if keychain else []):
        out[v] = None
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
