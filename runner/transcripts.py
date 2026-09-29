"""Transcript collection (symlink-safe) and model-pin verification (design §2, §11; review S-1, C-6, C-16).

`$CLAUDE_CONFIG_DIR/projects/` is written by the arm, so everything under it is hostile input: a symlink, a
hard link, a FIFO or a symlinked directory could make the host copy or hash a file outside the arm's tree
(or hang on a pipe). `safe_files` walks without following links and skips, and records, anything that is not
a plain single-link regular file whose real path stays under the root. Reads re-check with O_NOFOLLOW + fstat
so an entry swapped after the walk is still refused.

`verify_pin` checks the pinned model on every assistant message the turn produced — main session, subagents,
the product-owner agent — plus the stream's init model, Claude Code version, assistant events and
`result.modelUsage`. Checking nothing is a failure (`no_evidence`), never a vacuous pass.
`faults.classify_pin(report, who)` (Task 15, preflight m4) turns a report into a fault.
"""
from __future__ import annotations

import gzip, hashlib, json, os, stat
from dataclasses import dataclass, asdict, field
from pathlib import Path

from runner.config import Pins

OVERSIZE_MARKER = "bk_oversize_line"        # runner.session writes this in place of a line over its reader limit
UNSAFE_RECORD = "unsafe-entries.json"       # written into collect()'s dest when anything was skipped


def _open(p: Path):
    return gzip.open(p, "rt", errors="replace") if p.suffix == ".gz" else open(p, errors="replace")


def _rel(p: Path, root: Path) -> str:
    r = os.path.relpath(p, root)
    return "." if r == os.curdir else r


def _inside(p: Path, real_root: str) -> bool:
    return os.path.realpath(p).startswith(real_root + os.sep)


def safe_files(root: Path, pattern: str = "*.jsonl", *, skipped: list[dict] | None = None) -> list[Path]:
    """Plain regular files matching `pattern` under `root`, never following a link. Skipped entries are
    appended to `skipped` as {"path": <relative to root>, "reason": symlink|outside-root|not-regular|hardlinked}."""
    rec = skipped if skipped is not None else []
    if os.path.islink(root):
        rec.append({"path": ".", "reason": "symlink"})
        return []
    if not root.is_dir():
        return []
    real_root, out = os.path.realpath(root), []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            if (d / name).is_symlink():
                rec.append({"path": _rel(d / name, root), "reason": "symlink"})
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = d / name
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                rec.append({"path": _rel(p, root), "reason": "symlink"})
                continue
            if not p.match(pattern):
                continue
            reason = ("not-regular" if not stat.S_ISREG(st.st_mode) else
                      "hardlinked" if st.st_nlink != 1 else
                      "outside-root" if not _inside(p, real_root) else None)
            if reason:
                rec.append({"path": _rel(p, root), "reason": reason})
                continue
            out.append(p)
    return sorted(out)


def _read_safe(p: Path, real_root: str) -> bytes | None:
    """The file's bytes, or None when it is no longer a plain in-tree regular file (swapped after the walk)."""
    if not _inside(p.parent / "x", real_root):
        return None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            return None
        with os.fdopen(fd, "rb", closefd=False) as fh:
            return fh.read()
    finally:
        os.close(fd)


def _safe_contents(config_dir: Path, skipped: list[dict]) -> dict[str, bytes]:
    root = config_dir / "projects"
    files = safe_files(root, skipped=skipped)
    if not files:
        return {}
    real_root, out = os.path.realpath(root), {}
    for f in files:
        data = _read_safe(f, real_root)
        if data is None:
            skipped.append({"path": _rel(f, root), "reason": "changed-under-read"})
            continue
        out[_rel(f, root)] = data
    return out


def snapshot(config_dir: Path) -> dict[str, str]:
    """Relative path under `projects/` → sha256, for every safe transcript file."""
    return {rel: hashlib.sha256(b).hexdigest() for rel, b in _safe_contents(config_dir, []).items()}


def collect(config_dir: Path, before: dict[str, str], dest: Path, *,
            skipped: list[dict] | None = None) -> list[Path]:
    """Gzip every safe transcript that is new or changed since `before` into `dest/<rel>.gz` (recursive, so
    `<session>/subagents/*.jsonl` come too). Each file is read once: the bytes hashed are the bytes copied.
    Anything skipped is appended to `skipped` and recorded in `dest/unsafe-entries.json`."""
    rec: list[dict] = []
    out = []
    for rel, data in _safe_contents(config_dir, rec).items():
        if before.get(rel) == hashlib.sha256(data).hexdigest():
            continue
        target = dest / (rel + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(target, "wb") as dst:
            dst.write(data)
        out.append(target)
    if rec:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / UNSAFE_RECORD).write_text(json.dumps(rec, indent=2) + "\n")
    if skipped is not None:
        skipped.extend(rec)
    return sorted(out)


@dataclass
class PinReport:
    ok: bool
    assistant_messages: int
    stream_assistant_messages: int
    synthetic: int
    truncated_lines: int
    claude_code_versions: list[str]
    no_evidence: bool
    violations: list[dict] = field(default_factory=list)
    unverified_streams: list[str] = field(default_factory=list)   # streams with no init: version unproven

    def to_json(self) -> str:
        """The body of `model-pin.json`."""
        return json.dumps(asdict(self), indent=2)


def _lines(f: Path):
    with _open(f) as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                yield i, None
                continue
            yield i, ev if isinstance(ev, dict) else None


def verify_pin(transcript_files: list[Path], stream_files: list[Path], pins: Pins, *,
               require_transcripts: bool = True) -> PinReport:
    ok_models, synth = set(pins.accepted_models), set(pins.synthetic_models)
    n = sn = s = trunc = 0
    bad: list[dict] = []
    versions: set[str] = set()

    def judge(f, i, where, model):
        nonlocal s
        if model in synth:
            s += 1
        elif model not in ok_models:
            bad.append({"file": str(f), "line": i, "where": where, "model": model})

    for f in transcript_files:
        for i, ev in _lines(f):
            if ev is None:
                trunc += 1
            elif ev.get("type") == "assistant":
                n += 1
                judge(f, i, "assistant", (ev.get("message") or {}).get("model"))
    unverified: list[str] = []
    for f in stream_files:
        saw_init = active = False
        for i, ev in _lines(f):
            t = None if ev is None else ev.get("type")
            if ev is None or t == OVERSIZE_MARKER:       # a line nobody could inspect: counted, not fatal
                trunc += 1
            elif t == "system" and ev.get("subtype") == "init":
                saw_init = True
                judge(f, i, "init", ev.get("model"))
                v = ev.get("claude_code_version")
                versions.add(str(v))
                if v != pins.claude_version:
                    bad.append({"file": str(f), "line": i, "where": "claude_code_version", "model": v})
            elif t == "assistant":
                sn += 1; active = True
                judge(f, i, "stream.assistant", (ev.get("message") or {}).get("model"))
            elif t == "result":
                for m in (ev.get("modelUsage") or {}):
                    active = True
                    judge(f, i, "result.modelUsage", m)
        if not saw_init:
            # Controller ruling (concern 2): the version is never assumed. Activity without an init means the
            # model/version cannot be proven -> violation. No init and no activity (e.g. a turn that timed out
            # before starting) -> recorded as unverified, not a violation: the turn's own outcome carries it.
            versions.add("unverified")
            unverified.append(str(f))
            if active:
                bad.append({"file": str(f), "line": None, "where": "claude_code_version", "model": "unverifiable"})
    # Controller ruling: checking nothing is a failure. Transcripts are the evidence for an arm step (a broken
    # transcript-path assumption must fault, not pass on streams); with transcripts optional, SOME assistant
    # message must still have been inspected.
    no_evidence = (require_transcripts and n == 0) or (n + sn == 0)
    return PinReport(ok=not bad and not no_evidence, assistant_messages=n, stream_assistant_messages=sn,
                     synthetic=s, truncated_lines=trunc, claude_code_versions=sorted(versions),
                     no_evidence=no_evidence, violations=bad, unverified_streams=unverified)
