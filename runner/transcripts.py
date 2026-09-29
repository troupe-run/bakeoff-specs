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
  * any inspected field has the wrong JSON shape (reported as `<missing>` / `<malformed:TYPE>`, never raised);
  * a stream `result` of a turn that did work (a real assistant message, a tool_use, or total_cost_usd > 0) lacks
    a non-empty `modelUsage` dict with at least one real accepted model; a `modelUsage` that IS present must be a
    dict whose keys are all accepted (synthetic counted) whether or not the turn did work (fix round 2 (a): the runner captures the stream from container stdout, so the
    arm cannot edit it — this is the backstop for everything the transcript tree might hide);
  * a transcript file has no decodable line at all (`transcript_unverifiable`).
An undecodable line is tolerated (counted in `truncated_lines`) only when it is a file's LAST line, the file does
not end with a newline, no complete JSON object starts it (one that does is judged like any line, and its trailing
garbage is a violation), and no `"model": "<off-pin>"` pair is visible in it (every undecodable line is scanned,
with JSON-unescaped keys and values). In a stream, a visible `"type": "result"` in an unsalvageable line is a
violation too.

RESIDUAL RISK (fix round 2 (e)): the transcript-file check is best effort against a deliberately crafted
incomplete last line — e.g. an off-pin model string split or encoded so that no complete `"model": "..."` literal
pair survives in it. The stream's `result.modelUsage` rule is the backstop: the API's own per-model usage cannot
be forged from inside the container. Arms are spec methodologies, not adversaries; this defends against accidents
and sloppy tooling first, and makes deliberate evasion require defeating a record the arm cannot write.
`faults.classify_pin(report, who)` (Task 15, preflight m4) turns a report into a fault.
"""
from __future__ import annotations

import gzip, hashlib, json, os, re, stat
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
    """(line number, kind, payload): kind ok -> the decoded dict; bad -> the raw bytes (to be salvaged and
    scanned); oversize -> None. A line is never held beyond MAX_LINE_BYTES."""
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
                yield i, "bad", raw
                continue
            yield (i, "ok", ev) if isinstance(ev, dict) else (i, "bad", raw)


def _lines(f: Path) -> Iterator[tuple[int, str, object, bool]]:
    """_raw_lines plus whether each is the file's last non-empty line."""
    prev = None
    for item in _raw_lines(f):
        if prev is not None:
            yield (*prev, False)
        prev = item
    if prev is not None:
        yield (*prev, True)


_STR = r'"(?:[^"\\]|\\.)*"'
_KEY_VALUE = re.compile(rf"({_STR})\s*:\s*({_STR})")


def _unescape(literal: str) -> str | None:
    try:
        v = json.loads(literal)
    except (ValueError, RecursionError):
        return None
    return v if isinstance(v, str) else None


def _string_pairs(text: str) -> Iterator[tuple[str, str]]:
    """Every `"key": "value"` pair of JSON string literals in `text`, JSON-unescaped (so `"mod\\u0065l"` is
    `model`). Best effort over a line that does not decode — see the residual risk in the module docstring."""
    for k, v in _KEY_VALUE.findall(text):
        key, value = _unescape(k), _unescape(v)
        if key is not None and value is not None:
            yield key, value


def _salvage(raw: bytes) -> tuple[dict | None, str]:
    """A complete JSON object at the start of an undecodable line (and the text after it), else (None, text)."""
    text = raw.decode("utf-8", errors="replace").lstrip("﻿ \t\r\n")
    try:
        obj, end = json.JSONDecoder().raw_decode(text)
    except (ValueError, RecursionError):
        return None, text
    return (obj, text[end:]) if isinstance(obj, dict) else (None, text)


def _did_work(ev: dict, synthetic: set[str]) -> bool:
    """A stream assistant event is work if it is a real (non-synthetic) message or carries a tool_use."""
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return True                                       # unjudgeable: assume work (conservative)
    model = msg.get("model")
    if not (isinstance(model, str) and model in synthetic):
        return True
    content = msg.get("content")
    return isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content)


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

    def undecodable(f, i, kind, raw, last, on_event, *, stream: bool) -> None:
        """A line that did not decode: salvage a leading object, scan for model literals, and tolerate it only as
        a genuinely cut-off last line (no trailing newline, nothing salvageable, nothing off-pin visible)."""
        nonlocal trunc
        if kind == "oversize":
            violation(f, i, "oversize_line", UNINSPECTED)
            return
        obj, rest = _salvage(raw)
        if obj is not None:
            on_event(i, obj)                              # judged like any other line ...
            violation(f, i, "trailing_garbage", UNINSPECTED)   # ... and the garbage after it is never benign
        elif last and not raw.endswith(b"\n"):
            trunc += 1                                    # a timed-out turn's cut-off last line: counted
        else:
            violation(f, i, "unreadable_line", UNINSPECTED)
        for key, value in _string_pairs(rest):
            if key == "model":
                judge(f, i, "unreadable_line.model", value)
            elif stream and obj is None and key == "type" and value == "result":
                violation(f, i, "unreadable_result", UNINSPECTED)   # (a) the backstop itself is unreadable

    for f in transcript_files:
        decoded = 0

        def on_transcript(i, ev, f=f):
            nonlocal n, real_t, decoded
            decoded += 1
            if ev.get("type") == "assistant":
                n += 1
                real_t += judge_message(f, i, "assistant", ev)

        for i, kind, payload, last in _lines(f):
            if kind == "ok":
                on_transcript(i, payload)
            else:
                undecodable(f, i, kind, payload, last, on_transcript, stream=False)
        if decoded == 0:                                  # (d) nothing in this file could be checked
            violation(f, None, "transcript_unverifiable", "no-decodable-lines")

    for f in stream_files:
        st = {"init": False, "active": False, "work": False}

        def on_stream(i, ev, f=f, st=st):
            nonlocal sn, real_s, trunc
            t = ev.get("type")
            if t == OVERSIZE_MARKER:
                if outcomes.get(str(f)) in TRUNCATION_OK_OUTCOMES:
                    trunc += 1
                else:
                    violation(f, i, "oversize_marker", UNINSPECTED)
            elif t == "system" and ev.get("subtype") == "init":
                st["init"] = True
                judge(f, i, "init", ev.get("model"), allow_synthetic=False)
                v = ev.get("claude_code_version")
                versions.add(_shape(v))
                if not isinstance(v, str) or v != pins.claude_version:
                    violation(f, i, "claude_code_version", _shape(v))
            elif t == "assistant":
                sn += 1; st["active"] = True
                real_s += judge_message(f, i, "stream.assistant", ev)
                if _did_work(ev, synth):
                    st["work"] = True
            elif t == "result":
                # (a) The stream is runner-captured from container stdout, so the arm cannot edit it: every result
                # must account for its models — present, a non-empty dict, every key accepted (synthetic counted),
                # at least one key a real accepted model.
                # Ruling: required only when the turn did work (a real assistant message, a tool_use, or a cost);
                # a no-work error/auth result without it is not a pin fault — the turn's outcome carries that.
                # Whatever IS present must be well-formed and all-accepted regardless.
                st["active"] = True
                cost = ev.get("total_cost_usd")
                work = st["work"] or (cost is not None and not (isinstance(cost, (int, float)) and cost <= 0))
                mu = ev.get("modelUsage")
                if mu is None:
                    if work:
                        violation(f, i, "result.modelUsage", "<missing>")
                elif not isinstance(mu, dict):
                    violation(f, i, "result.modelUsage", _not_a_dict(mu))
                elif not mu:
                    if work:
                        violation(f, i, "result.modelUsage", "<empty>")
                elif not sum(judge(f, i, "result.modelUsage", m) for m in mu) and \
                        all(m in synth for m in mu) and work:
                    violation(f, i, "result.modelUsage", "<no-accepted-model>")

        for i, kind, payload, last in _lines(f):
            if kind == "ok":
                on_stream(i, payload)
            else:
                undecodable(f, i, kind, payload, last, on_stream, stream=True)
        if not st["init"]:
            # Controller ruling (concern 2): the version is never assumed. Activity without an init means the
            # model/version cannot be proven -> violation. No init and no activity (e.g. a turn that timed out
            # before starting) -> recorded as unverified, not a violation: the turn's own outcome carries it.
            versions.add("unverified")
            unverified.append(str(f))
            if st["active"]:
                violation(f, None, "claude_code_version", "unverifiable")
    # Controller rulings: checking nothing is a failure, and synthetic messages are not evidence. Transcripts are
    # the evidence for an arm step (a broken transcript-path assumption must fault, not pass on streams); with
    # transcripts optional, SOME real assistant message must still have been inspected.
    no_evidence = (require_transcripts and real_t == 0) or (real_t + real_s == 0)
    return PinReport(ok=not bad and not no_evidence, assistant_messages=n, stream_assistant_messages=sn,
                     synthetic=s, truncated_lines=trunc, claude_code_versions=sorted(versions),
                     no_evidence=no_evidence, violations=bad, unverified_streams=unverified)
