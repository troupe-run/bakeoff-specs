"""Transcript collection (symlink-safe) and model-pin verification (design §2, §11; review S-1, C-6, C-16).

`$CLAUDE_CONFIG_DIR/projects/` is written by the arm, so everything under it is hostile input: a symlink, a
hard link, a FIFO, a symlinked directory or a huge (sparse) file could make the host copy or hash a file outside
the arm's tree, hang on a pipe, or exhaust memory/disk. `safe_files` walks without following links and skips,
and records, anything that is not a plain single-link regular file of at most MAX_FILE_BYTES whose real path
stays under the root (and any directory it cannot list). Reads re-check with O_NOFOLLOW + fstat so an entry
swapped after the walk is still refused, and stream in CHUNK_BYTES pieces with the cap re-enforced.

`verify_pin` checks the pinned model on every assistant message the turn produced — main session, subagents,
the product-owner agent — plus the stream's init model, Claude Code version, assistant events and
`result.modelUsage`. It fails (never passes vacuously) when:
  * no REAL (non-synthetic) assistant message was inspected (`no_evidence`);
  * any entry of the transcript tree was skipped by collection (`unsafe`: the evidence is incomplete);
  * a line other than a file's last cannot be read, or any line exceeds MAX_LINE_BYTES;
  * a stream carries session.py's oversize marker on a turn whose outcome was not timeout/no_result
    (`stream_outcomes`; on those outcomes the marker is counted in `truncated_lines`, like a truncated last line);
  * any inspected field has the wrong JSON shape (reported as `<missing>` / `<malformed:TYPE>`, never raised).
`faults.classify_pin(report, who)` (Task 15, preflight m4) turns a report into a fault.
"""
from __future__ import annotations

import gzip, hashlib, json, os, stat
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, asdict, field
from pathlib import Path

from runner.config import Pins

OVERSIZE_MARKER = "bk_oversize_line"        # runner.session writes this in place of a line over its reader limit
UNSAFE_RECORD = "unsafe-entries.json"       # written into collect()'s dest when anything was skipped
MAX_FILE_BYTES = 256 * 1024 * 1024          # per transcript file; larger is skipped as "oversize" (fix round 1)
MAX_LINE_BYTES = 64 * 1024 * 1024           # per JSONL line when verifying; matches session.STREAM_LINE_LIMIT
CHUNK_BYTES = 1024 * 1024
TRUNCATION_OK_OUTCOMES = ("timeout", "no_result")   # session.TurnResult outcomes that may cut a stream short
UNINSPECTED = "<uninspected>"


def _rel(p: Path, root: Path) -> str:
    r = os.path.relpath(p, root)
    return "." if r == os.curdir else r


def _inside(p: Path, real_root: str) -> bool:
    return os.path.realpath(p).startswith(real_root + os.sep)


def safe_files(root: Path, pattern: str = "*.jsonl", *, skipped: list[dict] | None = None) -> list[Path]:
    """Plain regular files matching `pattern` under `root`, never following a link. Skipped entries are
    appended to `skipped` as {"path": <relative to root>,
    "reason": symlink|outside-root|not-regular|hardlinked|oversize|unreadable}."""
    rec = skipped if skipped is not None else []
    if os.path.islink(root):
        rec.append({"path": ".", "reason": "symlink"})
        return []
    if not root.is_dir():
        return []
    real_root, out = os.path.realpath(root), []
    def unlistable(e: OSError) -> None:            # os.walk silently drops what it cannot list; never here
        rec.append({"path": _rel(Path(e.filename), root), "reason": "unreadable"})
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=unlistable):
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
            try:
                st = os.lstat(p)
            except OSError:
                rec.append({"path": _rel(p, root), "reason": "unreadable"})
                continue
            if stat.S_ISLNK(st.st_mode):
                rec.append({"path": _rel(p, root), "reason": "symlink"})
                continue
            if not p.match(pattern):
                continue
            reason = ("not-regular" if not stat.S_ISREG(st.st_mode) else
                      "hardlinked" if st.st_nlink != 1 else
                      "oversize" if st.st_size > MAX_FILE_BYTES else
                      "outside-root" if not _inside(p, real_root) else None)
            if reason:
                rec.append({"path": _rel(p, root), "reason": reason})
                continue
            out.append(p)
    return sorted(out)




def _open_safe(p: Path, real_root: str) -> int | str:
    """An fd for `p` if it is still a plain in-tree single-link regular file within the cap, else the reason.
    O_NONBLOCK: opening a FIFO swapped in after the walk must not hang."""
    if not _inside(p.parent / "x", real_root):
        return "outside-root"
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return "symlink" if os.path.islink(p) else "unreadable"
    st = os.fstat(fd)
    reason = ("not-regular" if not stat.S_ISREG(st.st_mode) else
              "hardlinked" if st.st_nlink != 1 else
              "oversize" if st.st_size > MAX_FILE_BYTES else None)
    if reason:
        os.close(fd)
        return reason
    return fd


def _chunks(fd: int) -> Iterator[bytes]:
    """The file's bytes in CHUNK_BYTES pieces; raises _Oversize past MAX_FILE_BYTES (it grew after the fstat)."""
    total = 0
    while chunk := os.read(fd, CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise _Oversize
        yield chunk


class _Oversize(Exception):
    pass


def _each_safe(config_dir: Path, skipped: list[dict]) -> Iterator[tuple[str, int]]:
    """(relative path, open fd) for each safe transcript, one at a time; the caller closes the fd."""
    root = config_dir / "projects"
    files = safe_files(root, skipped=skipped)
    real_root = os.path.realpath(root) if files else ""
    for f in files:
        got = _open_safe(f, real_root)
        if isinstance(got, str):
            skipped.append({"path": _rel(f, root), "reason": "oversize" if got == "oversize" else "changed-under-read"})
            continue
        yield _rel(f, root), got


def snapshot(config_dir: Path) -> dict[str, str]:
    """Relative path under `projects/` → sha256, for every safe transcript file (streamed, one file at a time)."""
    out: dict[str, str] = {}
    for rel, fd in _each_safe(config_dir, []):
        try:
            h = hashlib.sha256()
            for chunk in _chunks(fd):
                h.update(chunk)
            out[rel] = h.hexdigest()
        except _Oversize:
            pass
        finally:
            os.close(fd)
    return out


def collect(config_dir: Path, before: dict[str, str], dest: Path, *,
            skipped: list[dict] | None = None) -> list[Path]:
    """Gzip every safe transcript that is new or changed since `before` into `dest/<rel>.gz` (recursive, so
    `<session>/subagents/*.jsonl` come too). Each file is read once, in chunks: the bytes hashed are the bytes
    copied. Anything skipped is appended to `skipped` and recorded in `dest/unsafe-entries.json`; pass the same
    list to `verify_pin(unsafe=...)`."""
    rec: list[dict] = []
    out = []
    for rel, fd in _each_safe(config_dir, rec):
        target = dest / (rel + ".gz")
        part = target.with_name(target.name + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        try:
            h = hashlib.sha256()
            with gzip.open(part, "wb") as dst:
                for chunk in _chunks(fd):
                    h.update(chunk)
                    dst.write(chunk)
        except _Oversize:
            part.unlink()
            rec.append({"path": rel, "reason": "oversize"})
            continue
        finally:
            os.close(fd)
        if before.get(rel) == h.hexdigest():
            part.unlink()
            continue
        part.replace(target)
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


def _raw_lines(f: Path) -> Iterator[tuple[int, str, object]]:
    """(line number, kind, event) with kind ok|bad|oversize. A line is never held beyond MAX_LINE_BYTES."""
    with (gzip.open(f, "rb") if f.suffix == ".gz" else open(f, "rb")) as fh:
        i = 0
        while raw := fh.readline(MAX_LINE_BYTES + 1):
            i += 1
            if len(raw) > MAX_LINE_BYTES and not raw.endswith(b"\n"):
                while (more := fh.readline(CHUNK_BYTES)) and not more.endswith(b"\n"):
                    pass
                yield i, "oversize", None
                continue
            if not raw.strip():
                continue
            try:
                ev = json.loads(raw)
            except (ValueError, RecursionError):
                yield i, "bad", None
                continue
            yield i, ("ok" if isinstance(ev, dict) else "bad"), ev


def _lines(f: Path) -> Iterator[tuple[int, str, object, bool]]:
    """_raw_lines plus whether each is the file's last non-empty line."""
    prev = None
    for item in _raw_lines(f):
        if prev is not None:
            yield (*prev, False)
        prev = item
    if prev is not None:
        yield (*prev, True)


def _not_a_dict(value: object) -> str:
    return "<missing>" if value is None else f"<malformed:{type(value).__name__}>"


def _shape(value: object) -> str:
    """The value if it is a string, else a tag naming what it is (so a hostile shape is reported, not raised)."""
    if isinstance(value, str):
        return value
    return "<missing>" if value is None else f"<malformed:{type(value).__name__}>"


def verify_pin(transcript_files: Iterable[Path], stream_files: Iterable[Path], pins: Pins, *,
               unsafe: list[dict], require_transcripts: bool = True,
               stream_outcomes: Mapping[Path | str, str] | None = None) -> PinReport:
    """`unsafe` is REQUIRED: collect()'s skipped entries. Any of them means the evidence is incomplete."""
    ok_models, synth = set(pins.accepted_models), set(pins.synthetic_models)
    outcomes = {str(k): v for k, v in (stream_outcomes or {}).items()}
    n = sn = real_t = real_s = s = trunc = 0
    bad: list[dict] = [{"file": e.get("path"), "line": None, "where": "transcript_unverifiable",
                        "model": e.get("reason")} for e in unsafe]
    versions: set[str] = set()
    unverified: list[str] = []

    def violation(f, i, where, model):
        bad.append({"file": str(f), "line": i, "where": where, "model": model})

    def judge(f, i, where, value, *, allow_synthetic=True) -> bool:
        """True when `value` is a real accepted model."""
        nonlocal s
        m = _shape(value)
        if isinstance(value, str) and value in synth and allow_synthetic:
            s += 1
            return False
        if isinstance(value, str) and value in ok_models:
            return True
        violation(f, i, where, m)
        return False

    def judge_message(f, i, where, ev) -> bool:
        msg = ev.get("message")
        if not isinstance(msg, dict):
            violation(f, i, where, _not_a_dict(msg))
            return False
        return judge(f, i, where, msg.get("model"))

    def unreadable(f, i, kind, last) -> None:
        nonlocal trunc
        if kind == "bad" and last:                       # a timed-out turn's cut-off last line: counted
            trunc += 1
        else:
            violation(f, i, "unreadable_line" if kind == "bad" else "oversize_line", UNINSPECTED)

    for f in transcript_files:
        for i, kind, ev, last in _lines(f):
            if kind != "ok":
                unreadable(f, i, kind, last)
            elif ev.get("type") == "assistant":
                n += 1
                real_t += judge_message(f, i, "assistant", ev)
    for f in stream_files:
        saw_init = active = False
        for i, kind, ev, last in _lines(f):
            if kind != "ok":
                unreadable(f, i, kind, last)
                continue
            t = ev.get("type")
            if t == OVERSIZE_MARKER:
                if outcomes.get(str(f)) in TRUNCATION_OK_OUTCOMES:
                    trunc += 1
                else:
                    violation(f, i, "oversize_marker", UNINSPECTED)
            elif t == "system" and ev.get("subtype") == "init":
                saw_init = True
                judge(f, i, "init", ev.get("model"), allow_synthetic=False)
                v = ev.get("claude_code_version")
                versions.add(_shape(v))
                if not isinstance(v, str) or v != pins.claude_version:
                    violation(f, i, "claude_code_version", _shape(v))
            elif t == "assistant":
                sn += 1; active = True
                real_s += judge_message(f, i, "stream.assistant", ev)
            elif t == "result" and "modelUsage" in ev:
                active = True
                mu = ev["modelUsage"]
                if not isinstance(mu, dict):
                    violation(f, i, "result.modelUsage", _not_a_dict(mu))
                else:
                    for m in mu:
                        judge(f, i, "result.modelUsage", m)
        if not saw_init:
            # Controller ruling (concern 2): the version is never assumed. Activity without an init means the
            # model/version cannot be proven -> violation. No init and no activity (e.g. a turn that timed out
            # before starting) -> recorded as unverified, not a violation: the turn's own outcome carries it.
            versions.add("unverified")
            unverified.append(str(f))
            if active:
                violation(f, None, "claude_code_version", "unverifiable")
    # Controller rulings: checking nothing is a failure, and synthetic messages are not evidence. Transcripts are
    # the evidence for an arm step (a broken transcript-path assumption must fault, not pass on streams); with
    # transcripts optional, SOME real assistant message must still have been inspected.
    no_evidence = (require_transcripts and real_t == 0) or (real_t + real_s == 0)
    return PinReport(ok=not bad and not no_evidence, assistant_messages=n, stream_assistant_messages=sn,
                     synthetic=s, truncated_lines=trunc, claude_code_versions=sorted(versions),
                     no_evidence=no_evidence, violations=bad, unverified_streams=unverified)
