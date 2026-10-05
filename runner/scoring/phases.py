"""Time and cost by phase (spec §5): the method's own phases (one turn = one phase, labelled by its command) and
seven common phases classified from transcript events by the rules in scoring/phases.toml.

Turn boundaries come from the transcripts themselves: every top-level user entry that is not a tool result, not
meta, not a compaction summary and not harness-originated (an `origin`, e.g. a background task's notification) is
a turn prompt, emitted as an `other` event named "(prompt)" with `input = {"label": ...}`.
The gap that ends at a prompt (or at the queue operations that hand it in) is between turns (the PO or the owner is answering) and counts as no arm phase; that
time is `waiting`, taken from run.json."""
from __future__ import annotations
import fnmatch
import functools
import gzip
import json
import re
import zlib
from datetime import datetime
from pathlib import Path
from runner import transcripts
from runner.scoring import evidence, values

PHASES = ("understand", "specify", "implement", "test", "rework", "review", "waiting")
PROMPT = "(prompt)"
QUEUE = "(queue)"                                         # a queue-operation entry: the harness handing in a prompt
FREE_TEXT = "(free text)"
OUTPUT_CHARS = 4000
TRANSCRIPT_CHAR_CAP = 256 * 1024 * 1024                   # decompressed characters read per transcript file
_WRITE = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
_QUOTED = re.compile(r"""'[^']*'|"(?:[^"\\]|\\.)*\"""")        # shell strings: emptied in the shell text (_shell)
# a heredoc: delimiter (2), the rest of its header line (3), its body (4, from the header's newline) up to the
# terminator line, or to the end of the command when it has none; an empty body is allowed; `<<<` is a here-string.
# Only matched where _heredocs() finds a `<<` at shell level (not in quotes, not in (( )) / $(( )) arithmetic).
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?[ \t]*(['\"]?)([A-Za-z_]\w*)\1([^\n]*)(.*?)(?:\n[ \t]*\2[ \t]*(?=\n|$)|\Z)",
                      re.S)
_COMPARISON = re.compile(r"\[\[.*?\]\]|\(\(.*?\)\)")          # [[ a > b ]] and (( a > b )) are not redirects
_SIMPLE_COMMAND = re.compile(r"\n|&&|\|\||\$\(|[;&|(){}`]")
_PARAM = re.compile(r"\$\{[^{}]*\}")                          # ${d}: a parameter expansion, not a { } group
_COMMAND_NAME = re.compile(r"<command-name>\s*(/\S+?)\s*</command-name>")
_CALL_NAMES = ("skill", "description", "subagent_type")   # not the prompt: it may say "verify" about anything
_STEM = re.compile(r"^arm-a(\d+)-(\d+)$")


def _match(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.replace("/**", "")) for g in globs)


def _spec(path, rules, spec_paths) -> bool:
    return _match(path, rules.spec_globs) or any(
        path.startswith(sp.path) if sp.path.endswith("/") else fnmatch.fnmatch(path, sp.path) for sp in spec_paths)


def _rel(path) -> str:
    return re.sub(r"^/work/[^/]+/", "", path) if isinstance(path, str) else ""


def _arith_end(command: str, i: int) -> int:
    """The index just past the `))` closing the `((` at i (or the end of the command)."""
    depth, j = 0, i
    while j < len(command):
        if command[j] == "(":
            depth += 1
        elif command[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return j


def _scan(command: str) -> tuple[list[re.Match], list[tuple[int, int]]]:
    """The command's heredocs and comments, in order, as the shell reads them: a `<<WORD` operator or a `#` comment
    (at the start of a word) only outside quotes and outside (( )) / $(( )) arithmetic; a heredoc's body and a
    comment are not scanned further (an apostrophe in `# the command's actor` opens no quote)."""
    out, comments, i, n = [], [], 0, len(command)
    while i < n:
        c = command[i]
        if c == "#" and (i == 0 or command[i - 1] in " \t\n;&|("):
            j = command.find("\n", i)
            j = n if j < 0 else j
            comments.append((i, j))
            i = j
        elif c == "\\":
            i += 2
        elif c == "'":
            j = command.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif c == '"':
            j = i + 1
            while j < n and command[j] != '"':
                j += 2 if command[j] == "\\" else 1
            i = j + 1
        elif command.startswith("((", i):
            i = _arith_end(command, i)
        elif command.startswith("<<", i):
            m = _HEREDOC.match(command, i)
            if m:
                out.append(m)
                i = m.end()
            else:
                i += 2 + (command.startswith("<", i + 2))
        else:
            i += 1
    return out, comments


def _heredocs(command: str) -> list[re.Match]:
    return _scan(command)[0]


def _without_heredoc_bodies(command: str) -> str:
    """The command with each heredoc's body and each comment removed (the heredoc's header line is kept)."""
    heredocs, comments = _scan(command)
    cuts = sorted([(m.start(), m.end(), "<<" + m[2] + m[3]) for m in heredocs] + [(a, b, "") for a, b in comments])
    parts, last = [], 0
    for a, b, keep in cuts:
        parts += [command[last:a], keep]
        last = b
    return "".join(parts) + command[last:]


def _shell(command: str) -> str:
    """The shell text of a Bash command: heredoc bodies removed, quoted strings emptied, [[ ]] / (( )) blanked."""
    text = _QUOTED.sub(lambda m: m[0][0] * 2, _without_heredoc_bodies(command))
    return _COMPARISON.sub(lambda m: m[0][:2] + "  " + m[0][-2:], text)


def is_test_command(command: str, rules) -> bool:
    """True when a `test_commands` regex matches at the start of one of the command's simple commands (shell text
    only, `command_prefixes` stripped first): `uv run pytest` is a test run, `grep pytest` is not. Also true when
    a `test_calls` regex matches code the call feeds an interpreter (`pytest.main(...)` in a python heredoc)."""
    if any(r.search(code) for code in _code_texts(command, rules) for r in rules.test_calls):
        return True
    for part in _SIMPLE_COMMAND.split(_PARAM.sub("$_", _shell(command))):
        part = part.lstrip()
        stripped = True
        while stripped:
            stripped = False
            for r in rules.command_prefixes:
                m = r.match(part)
                if m and m.end() > 0:
                    part, stripped = part[m.end():].lstrip(), True
                    break
        if any(r.match(part) for r in rules.test_commands):
            return True
    return False


@functools.lru_cache(maxsize=None)
def _interpreter_rx(patterns: tuple[str, ...]) -> tuple[str, re.Pattern, re.Pattern]:
    """(the interpreter command word as a regex source, that word standing alone, an interpreter call with a -c
    string in group "code")."""
    word = rf"(?:^|(?<=[\s;&|(]))(?:\S*/)?(?:{'|'.join(patterns)})"
    return (word, re.compile(word + r"(?=[\s;&|)]|$)"),
            re.compile(word + r"""\s+(?:-\w+\s+)*-c\s+(?P<code>'[^']*'|"(?:[^"\\]|\\.)*")"""))


def _code_texts(command: str, rules) -> list[str]:
    """The code a Bash call feeds an interpreter: heredoc bodies of interpreter commands (`python3 - <<EOF`), heredocs
    saved to a script that the same call then runs with one (`cat > /tmp/p.py <<EOF ... EOF; python3 /tmp/p.py`),
    and -c strings."""
    word_src, word, dash_c = _interpreter_rx(tuple(r.pattern for r in rules.code_interpreters))
    out = []
    for m in _heredocs(command):
        start = max(command.rfind(c, 0, m.start()) for c in "\n;&") + 1
        header = command[start:m.start()] + re.split(r"[;&]", m[3], maxsplit=1)[0]
        saved = [g.strip("'\"") for r in rules.write_commands for x in r.finditer(header)   # the script it saves to
                 if (g := x.groupdict().get("path"))]
        runs_saved = any(re.search(word_src + r"\s+(?:-\S+\s+)*" + re.escape(p) + r"(?![^\s;&|)])",
                                   command[m.end():]) for p in saved)
        if word.search(header) or runs_saved:
            out.append(m[4])
    for m in dash_c.finditer(_without_heredoc_bodies(command)):
        code = m["code"][1:-1]
        out.append(re.sub(r'\\(["\\$`])', r"\1", code) if m["code"][0] == '"' else code)
    return out


def _assigned(before: str, var: str) -> str | None:
    """The last string literal assigned to `var` in `before` (`p = 'src/a.py'`), if any."""
    found = re.findall(rf"\b{re.escape(var)}\s*=\s*(['\"])([^'\"\n]+)\1", before)
    return found[-1][1] if found else None


def bash_write_targets(command: str, rules) -> list[str] | None:
    """None when `command` writes no repo file; else its repo-relative targets in order ([] when it writes but
    names no readable target). Rules: `write_commands` over the shell text (heredoc bodies removed, quoted strings
    emptied, [[ ]] / (( )) comparisons blanked: a `>` inside a sed expression, an echo or a test is not a redirect),
    `write_calls` only over the code fed to an interpreter (_code_texts: python heredoc bodies, heredoc scripts the
    call runs, python -c strings); a target
    outside the repo (absolute after /work/<repo>/ is cut) is ignored, and a command whose only targets are outside
    the repo is not a write."""
    targets, unnamed = [], False
    passes = [(rules.write_commands, _shell(command))] + [(rules.write_calls, c) for c in _code_texts(command, rules)]
    for regexes, text in passes:
        for r in regexes:
            for m in r.finditer(text):
                g = m.groupdict()
                p = g.get("path") or (_assigned(text[:m.start()], g["var"]) if g.get("var") else None)
                if p is None:
                    unnamed = True
                    continue
                p = _rel(p.strip("'\""))
                if p and not p.startswith("/") and p not in targets:
                    targets.append(p)
    return targets if targets else ([] if unnamed else None)


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
    """Indices that open a turn: each prompt, and everything from the earliest queue operation in the run of
    plain entries just before it (the harness handing the prompt in: queue ops, attachments, ...)."""
    out = set()
    for i, e in enumerate(events):
        if not _is_prompt(e):
            continue
        out.add(i)
        j, first_queue = i - 1, None
        while j >= 0 and events[j]["kind"] == "other" and not _is_prompt(events[j]):
            if events[j]["name"] == QUEUE:
                first_queue = j
            j -= 1
        if first_queue is not None:
            out.update(range(first_queue, i))
    return out


def classify(events: list[dict], rules, spec_paths) -> dict:
    """Seconds per phase over time-ordered events (rules 1-6 of the brief; `waiting` is left 0 here). Also returns
    `by_turn`: the same split per turn prompt (time before the first prompt joins the first turn).

    One state machine runs over the whole interleaved timeline: the main session and every subagent session merged
    by time. Rework mode, the current phase and "has written this turn" are shared, so a subagent's failing test
    run puts the main loop's next write into rework, and a gap is attributed to whichever session's event came
    first. Keep this in mind when checking the owner's sample: per-session state would split differently."""
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
            lab = e["input"].get("label") if isinstance(e["input"], dict) else None
            review_turn = isinstance(lab, str) and any(r.search(lab) for r in rules.review_markers)
            phase = current
        elif e["kind"] == "result":
            if e["id"] in pending:                        # rules 3-4: a test result sets or clears rework mode
                out = e.get("output") or ""
                rework = bool(e["is_error"]) or any(r.search(out) for r in rules.failure_markers)
                pending.discard(e["id"])
        elif e["kind"] == "tool":
            name, inp = e["name"], e["input"] if isinstance(e["input"], dict) else {}
            cmd = inp.get("command", "") if name == "Bash" and isinstance(inp.get("command"), str) else ""
            bash_targets = bash_write_targets(cmd, rules) if cmd else None
            if cmd and is_test_command(cmd, rules):
                phase = "test"                            # a test run dominates a call's time, even if it also writes
                wrote = wrote or bash_targets is not None
                if e.get("id"):
                    pending.add(e["id"])
            elif name in _WRITE or bash_targets is not None:    # rule 2, and Bash writes (R10)
                path = (_rel(inp.get("file_path") or inp.get("notebook_path") or "") if name in _WRITE
                        else (bash_targets or [None])[0])
                base = ("implement" if path is None else "specify" if _spec(path, rules, spec_paths)
                        else "test" if _match(path, rules.test_globs) else "implement")
                phase, wrote = ("rework" if rework else base), True
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
        return "\n".join(b["text"] for b in content
                         if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    return ""


_PATH_KEYS = ("file_path", "notebook_path", "command")


def _malformed(blocks: list[dict]) -> bool:
    """A content block of the wrong shape: non-string text, a tool call whose input is not an object or whose path
    or command is not a string, a tool result whose content is neither text nor a list of blocks."""
    for b in blocks:
        kind = b.get("type")
        if kind == "text" and not isinstance(b.get("text"), str):
            return True
        if kind == "tool_use":
            inp = b.get("input")
            if inp is not None and not isinstance(inp, dict):
                return True
            if isinstance(inp, dict) and any(k in inp and not isinstance(inp[k], str) for k in _PATH_KEYS):
                return True
        if kind == "tool_result" and not isinstance(b.get("content"), (str, list, type(None))):
            return True
        if kind == "tool_result" and isinstance(b.get("content"), list) and _malformed(
                [x for x in b["content"] if isinstance(x, dict)]):
            return True
    return False


def _clean_input(inp) -> dict:
    if not isinstance(inp, dict):
        return {}
    return {k: v for k, v in inp.items() if k not in _PATH_KEYS or isinstance(v, str)}


def _entry_events(o: dict, t: float, session: str) -> tuple[list[dict], bool]:
    """The entry's events (at least one) and whether any of its blocks was malformed (repaired, counted skipped)."""
    base = {"t": t, "kind": "other", "name": None, "input": {}, "is_error": False, "id": None, "output": "",
            "session": session}
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    content = msg.get("content")
    blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
    bad = _malformed(blocks)
    out = []
    if o.get("type") == "assistant":
        out = [{**base, "kind": "tool", "name": b.get("name"), "input": _clean_input(b.get("input")), "id": b.get("id")}
               for b in blocks if b.get("type") == "tool_use"]
    elif o.get("type") == "user":
        out = [{**base, "kind": "result", "id": b.get("tool_use_id"), "is_error": bool(b.get("is_error")),
                "output": _text(b.get("content"))[-OUTPUT_CHARS:]} for b in blocks if b.get("type") == "tool_result"]
        if not out and not o.get("isSidechain") and not o.get("isMeta") and not o.get("isCompactSummary") \
                and not o.get("origin") and (isinstance(content, str) or blocks):   # origin: task notifications
            out = [{**base, "name": PROMPT, "input": {"label": label(_text(content))}}]
    elif o.get("type") == "queue-operation":
        out = [{**base, "name": QUEUE}]
    return out or [base], bad


def events_from_transcripts(dir: Path, *, skipped_files: list[dict] | None = None) -> tuple[list[dict], int]:
    """All events of the session transcripts under `dir` (subagent sessions included), sorted by time, and the
    number of lines that could not be parsed (or held a malformed block: repaired, kept, counted). Files
    `safe_files` refuses are appended to `skipped_files`; so is a file that could not be read to its end
    (`"reason": "truncated" | "corrupt" | "unreadable" | "over-size-cap"`, with the `kept_lines` read before that
    point, whose events are kept; the lost rest counts as one skipped line). At most TRANSCRIPT_CHAR_CAP
    decompressed characters are read per file."""
    keyed, skipped = [], 0
    rec = skipped_files if skipped_files is not None else []
    for fi, f in enumerate(transcripts.safe_files(dir, "*.jsonl*", skipped=skipped_files)):
        session = str(f.relative_to(dir))
        lines, cut = _read_lines(f)
        if cut:
            skipped += 1
            rec.append({"path": session, "reason": cut, "kept_lines": len(lines)})
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
            evs, bad = _entry_events(o, t, session)
            skipped += bad
            for bi, e in enumerate(evs):
                keyed.append(((t, fi, li, bi), e))
    keyed.sort(key=lambda x: x[0])
    return [e for _, e in keyed], skipped


def _read_lines(f: Path) -> tuple[list[str], str | None]:
    """The file's lines, read one at a time, and why reading stopped early (None when it reached the end)."""
    lines, total = [], 0
    opener = gzip.open if f.name.endswith(".gz") else open
    try:
        with opener(f, "rt", errors="replace") as fh:
            while True:
                line = fh.readline(TRANSCRIPT_CHAR_CAP - total + 1)
                if not line:
                    return lines, None
                total += len(line)
                if total > TRANSCRIPT_CHAR_CAP:
                    return lines, "over-size-cap"
                lines.append(line)
    except EOFError:
        return lines, "truncated"
    except (zlib.error, gzip.BadGzipFile):
        return lines, "corrupt"
    except OSError:
        return lines, "unreadable"


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
    """(first, last) event time of each top-level turn in the attempt's transcripts, in order; None if none. A turn
    opens at its earliest queue operation (else its prompt) and ends at its last entry before the next turn opens,
    background-subagent entries included (R12)."""
    evs, _ = events_from_transcripts(step_dir / "transcripts" / f"a{attempt}")
    opening = _turn_starts(evs)
    prompts = [i for i, e in enumerate(evs) if _is_prompt(e)]
    if not prompts:
        return None
    starts = []
    for p in prompts:
        while p - 1 in opening:
            p -= 1
        starts.append(p)
    ends = starts[1:] + [len(evs)]
    return [(evs[s]["t"], evs[max(s, e - 1)]["t"]) for s, e in zip(starts, ends)]


def killed_turn_seconds(step_dir: Path, stem: str, spans: list[tuple[float, float]] | None) -> float | None:
    """The span of a killed turn's transcript entries (evidence._killed_seconds), or None when it has none. `spans`
    is turn_spans() of the turn's attempt, computed once by the caller."""
    m = _STEM.match(stem)
    if not m:
        return None
    attempt = int(m[1])
    stems = sorted(f.name.removesuffix(".stream.jsonl.gz") for f in (step_dir / "turns").glob(
        f"arm-a{attempt}-*.stream.jsonl.gz"))
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
