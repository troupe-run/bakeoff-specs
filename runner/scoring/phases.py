"""Time and cost by phase (spec §5): the method's own phases (one turn = one phase, labelled by its command) and
seven common phases classified from transcript events by the rules in scoring/phases.toml.

Turn boundaries come from the transcripts themselves: every top-level user entry that is not a tool result, not
meta, not a compaction summary and not harness-originated (an `origin`, e.g. a background task's notification) is
a turn prompt, emitted as an `other` event named "(prompt)" with `input = {"label": ...}`.
The gap that ends at a prompt (or at the queue operations that hand it in) is between turns (the PO or the owner is answering) and counts as no arm phase; that
time is `waiting`, taken from run.json."""
from __future__ import annotations
import fnmatch
import gzip
import json
import re
from datetime import datetime
from pathlib import Path
from runner import transcripts
from runner.scoring import evidence, values

PHASES = ("understand", "specify", "implement", "test", "rework", "review", "waiting")
PROMPT = "(prompt)"
QUEUE = "(queue)"                                         # a queue-operation entry: the harness handing in a prompt
FREE_TEXT = "(free text)"
OUTPUT_CHARS = 4000
_WRITE = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
_FAILED = re.compile(r"(?i)\b(failed|error)\b")
_COMMAND_NAME = re.compile(r"<command-name>\s*(/\S+?)\s*</command-name>")
_CALL_NAMES = ("skill", "description", "subagent_type")   # not the prompt: it may say "verify" about anything
_STEM = re.compile(r"^arm-a(\d+)-(\d+)$")


def _match(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.replace("/**", "")) for g in globs)


def _spec(path, rules, spec_paths) -> bool:
    return _match(path, rules.spec_globs) or any(
        path.startswith(sp.path) if sp.path.endswith("/") else fnmatch.fnmatch(path, sp.path) for sp in spec_paths)


def _rel(path: str) -> str:
    return re.sub(r"^/work/[^/]+/", "", path or "")


def label(prompt: str) -> str:
    """A turn's method label: its slash command when it opens with one, else "(free text)"."""
    m = _COMMAND_NAME.search(prompt)
    if m:
        return m[1]
    tokens = prompt.split()
    return tokens[0] if tokens and tokens[0].startswith("/") else FREE_TEXT


def _is_prompt(e: dict) -> bool:
    return e["kind"] == "other" and e["name"] == PROMPT


def _turn_starts(events: list[dict]) -> set[int]:
    """Indices that open a turn: each prompt, and the queue operations that directly precede it."""
    out, opening = set(), False
    for i in range(len(events) - 1, -1, -1):
        e = events[i]
        if _is_prompt(e):
            out.add(i)
            opening = True
        elif opening and e["kind"] == "other" and e["name"] == QUEUE:
            out.add(i)
        else:
            opening = False
    return out


def classify(events: list[dict], rules, spec_paths) -> dict:
    """Seconds per phase over time-ordered events (rules 1-6 of the brief; `waiting` is left 0 here). Also returns
    `by_turn`: the same split per turn prompt (time before the first prompt joins the first turn)."""
    secs = {p: 0.0 for p in PHASES}
    by_turn: list[dict] = []
    rework, wrote, current, pending, review_turn, prompts = False, False, "understand", set(), False, 0
    last_of_session = {e.get("session"): i for i, e in enumerate(events)}
    starts = _turn_starts(events)
    for i, e in enumerate(events):
        nxt = events[i + 1] if i + 1 < len(events) else None
        gap = 0.0 if (nxt is None or last_of_session[e.get("session")] == i or i + 1 in starts) \
            else max(0.0, nxt["t"] - e["t"])
        phase = current
        if _is_prompt(e):                                 # a new turn: understanding again, unless it is a review
            prompts += 1
            if prompts > 1 or not by_turn:
                by_turn.append({p: 0.0 for p in PHASES})
            wrote, current = False, "understand"
            review_turn = any(r.search((e["input"] or {}).get("label", "")) for r in rules.review_markers)
            phase = current
        elif e["kind"] == "result":
            if e["id"] in pending:                        # rules 3-4: a test result sets or clears rework mode
                rework = bool(e["is_error"]) or bool(_FAILED.search(e.get("output") or ""))
                pending.discard(e["id"])
        elif e["kind"] == "tool":
            name, inp = e["name"], e["input"] or {}
            if name in _WRITE:
                path = _rel(inp.get("file_path") or inp.get("notebook_path") or "")
                base = ("specify" if _spec(path, rules, spec_paths) else "test" if _match(path, rules.test_globs)
                        else "implement")
                phase, wrote = ("rework" if rework else base), True
            elif name == "Bash" and any(r.search(inp.get("command", "")) for r in rules.test_commands):
                phase = "test"
                if e.get("id"):
                    pending.add(e["id"])
            elif name in ("Skill", "Task", "Agent") and any(    # the skill's name, the task's description/type
                    r.search(" ".join(str(inp.get(k, "")) for k in _CALL_NAMES)) for r in rules.review_markers):
                phase = "review"
            elif not wrote:
                phase = "understand"
            current = phase
        if review_turn:                                   # rule 5: a turn labelled as review is review throughout
            phase = "review"
        if not by_turn:
            by_turn.append({p: 0.0 for p in PHASES})
        secs[phase] += gap
        by_turn[-1][phase] += gap
    return {"seconds": secs, "skipped_lines": 0, "by_turn": by_turn, "prompts": prompts}


def _epoch(ts) -> float | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _entry_events(o: dict, t: float, session: str) -> list[dict]:
    base = {"t": t, "kind": "other", "name": None, "input": {}, "is_error": False, "id": None, "output": "",
            "session": session}
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    content = msg.get("content")
    blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
    out = []
    if o.get("type") == "assistant":
        out = [{**base, "kind": "tool", "name": b.get("name"), "input": b.get("input") or {}, "id": b.get("id")}
               for b in blocks if b.get("type") == "tool_use"]
    elif o.get("type") == "user":
        out = [{**base, "kind": "result", "id": b.get("tool_use_id"), "is_error": bool(b.get("is_error")),
                "output": _text(b.get("content"))[:OUTPUT_CHARS]} for b in blocks if b.get("type") == "tool_result"]
        if not out and not o.get("isSidechain") and not o.get("isMeta") and not o.get("isCompactSummary") \
                and not o.get("origin") and (isinstance(content, str) or blocks):   # origin: task notifications
            out = [{**base, "name": PROMPT, "input": {"label": label(_text(content))}}]
    elif o.get("type") == "queue-operation":
        out = [{**base, "name": QUEUE}]
    return out or [base]


def events_from_transcripts(dir: Path, *, skipped_files: list[dict] | None = None) -> tuple[list[dict], int]:
    """All events of the session transcripts under `dir` (subagent sessions included), sorted by time, and the
    number of lines that could not be parsed. Files `safe_files` refuses are appended to `skipped_files`."""
    keyed, skipped = [], 0
    for fi, f in enumerate(transcripts.safe_files(dir, "*.jsonl*", skipped=skipped_files)):
        session = str(f.relative_to(dir))
        try:
            opener = gzip.open if f.name.endswith(".gz") else open
            with opener(f, "rt", errors="replace") as fh:
                lines = list(fh)
        except (OSError, EOFError):
            skipped += 1                                  # an unreadable or truncated file counts as one bad line
            continue
        for li, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(o, dict):
                skipped += 1
                continue
            if "timestamp" not in o:
                continue                                  # bookkeeping entries (last-prompt, ...) carry no time
            t = _epoch(o["timestamp"])
            if t is None:
                skipped += 1
                continue
            for bi, e in enumerate(_entry_events(o, t, session)):
                keyed.append(((t, fi, li, bi), e))
    keyed.sort(key=lambda x: x[0])
    return [e for _, e in keyed], skipped


def method_phases(step_dir: Path) -> dict:
    """One phase per turn of the final attempt, labelled by the turn's command, with its seconds and cost."""
    t = evidence.arm_time(step_dir)
    if values.is_missing(t):
        return t
    out = []
    for turn in t["value"]["turns"]:
        p = step_dir / "turns" / f"{turn['stem']}.prompt.md"
        try:
            lab = label(p.read_text(errors="replace"))
        except OSError:
            lab = "(prompt unreadable)"
        out.append({"stem": turn["stem"], "label": lab, "seconds": turn["seconds"], "usd": turn["usd"]})
    return values.val(out, t["source"])


def turn_spans(step_dir: Path, attempt: int) -> list[tuple[float, float]] | None:
    """(first, last) event time of each top-level turn in the attempt's transcripts, in order; None if none."""
    evs, _ = events_from_transcripts(step_dir / "transcripts" / f"a{attempt}")
    starts = [i for i, e in enumerate(evs) if _is_prompt(e)]
    if not starts:
        return None
    ends = starts[1:] + [len(evs)]
    return [(evs[s]["t"], evs[e - 1]["t"]) for s, e in zip(starts, ends)]


def killed_turn_seconds(step_dir: Path, stem: str) -> float | None:
    """The span of a killed turn's transcript entries (evidence._killed_seconds), or None when it has none."""
    m = _STEM.match(stem)
    if not m:
        return None
    attempt = int(m[1])
    stems = sorted(f.name.removesuffix(".stream.jsonl.gz") for f in (step_dir / "turns").glob(
        f"arm-a{attempt}-*.stream.jsonl.gz"))
    spans = turn_spans(step_dir, attempt)
    if stem not in stems or spans is None or stems.index(stem) >= len(spans):
        return None
    first, last = spans[stems.index(stem)]
    return last - first if last > first else None


def _split_usd(turns: list[dict], by_turn: list[dict]) -> tuple[dict, list[str]]:
    """Each turn's cost split by its own phase seconds. A turn with unknown cost (killed, or no total) is paid by
    the next known turn's difference, so that cost is split over both turns' seconds; a known cost on a turn with
    no classified time waits for the next turn that has some. Returns (usd, stems whose cost is not placed)."""
    usd = {p: 0.0 for p in PHASES}
    carry_secs, carry_usd, carry_stems = {p: 0.0 for p in PHASES}, 0.0, []
    for turn, split in zip(turns, by_turn):
        for p in PHASES:
            carry_secs[p] += split[p]
        carry_stems.append(turn["stem"])
        if turn.get("usd") is None:
            continue
        carry_usd += turn["usd"]
        total = sum(carry_secs.values())
        if total > 0:
            for p in PHASES:
                usd[p] += carry_usd * carry_secs[p] / total
            carry_secs, carry_usd, carry_stems = {p: 0.0 for p in PHASES}, 0.0, []
    return usd, carry_stems


def common_phases(step_dir: Path, spec_paths, rules) -> dict:
    """Seconds and cost in each of the seven common phases for the step's final attempt."""
    r = evidence.run_record(step_dir)
    if values.is_missing(r):
        return r
    po, owner = r["value"].get("po_seconds"), r["value"].get("owner_wait_seconds")
    if not all(isinstance(x, (int, float)) for x in (po, owner)):
        return values.missing(r["source"], "run.json lacks po_seconds or owner_wait_seconds")
    t = evidence.arm_time(step_dir)
    if values.is_missing(t):
        return t
    tdir = step_dir / "transcripts" / f"a{t['value']['attempt']}"
    refused: list[dict] = []
    evs, skipped = events_from_transcripts(tdir, skipped_files=refused)
    if not evs:
        return values.missing(evidence.rel(tdir), "no transcript events" + (f"; refused {refused}" if refused else ""))
    c = classify(evs, rules, spec_paths)
    seconds = dict(c["seconds"], waiting=float(po + owner))
    out = {"seconds": seconds, "usd": None, "skipped_lines": skipped}
    turns = t["value"]["turns"]
    if c["prompts"] != len(turns):
        out["usd_why"] = (f"{c['prompts']} turn prompts in the transcripts, {len(turns)} turn records: "
                          "cost cannot be placed per turn")
    else:
        usd, unpaid = _split_usd(turns, c["by_turn"])
        out["usd"] = usd
        if unpaid:
            out["usd_why"] = f"cost unknown for {', '.join(unpaid)} (killed or no total): not included"
    if refused:
        out["skipped_files"] = refused
    return values.val(out, evidence.rel(tdir))
