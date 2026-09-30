"""The live per-turn feed and `runner watch` (owner request: see a real run going off the rails, and stop it).

A turn's stream is only written gzipped as evidence (`session.run_turn`), which cannot be followed while it is
written. So each turn ALSO writes a plain, line-buffered, human-readable feed — one line per stream event of
interest — and `runner watch` follows it from a second terminal.

Where (state, never results/): `state/<pass>/<arm>/live/`
  * `NN-<run>-<stem>-<started>.log`  one file per turn. `NN` is the step (so `secrets.scan_step` can pick a step's
    feeds), `<run>` is `a`/`b` (the step's N.a / N.b), `setup` or `-`, `<stem>` is `session.stem` (role, attempt,
    turn number) and `<started>` a UTC timestamp, so a re-run of the same turn never overwrites an earlier feed.
  * `current.json`  written atomically when a turn starts, removed when it ends: which feed is live, plus the
    header facts and the runner's pid. `watch` reads only this pointer: no directory-mtime heuristics, and a
    runner killed without cleanup (SIGKILL) leaves a pointer whose pid is dead, which `watch` ignores. One pointer
    per arm dir: arms never share one, so concurrent arms cannot clobber each other's.
  The arm's containers never see this directory (`state/<pass>/<arm>/` itself is never mounted; only `home/`,
  `work/` and single inbox files are).

Secrets: every line is passed through `secrets.live_redactor` (token shapes, the OAuth token, the dry-run dummy,
the arm home's PAT values, and their encodings) BEFORE it is trimmed and written: a raw credential is never
written. The files are still scanned like the stream they mirror: `secrets.scan_step` (after every run) and
`secrets.scan_arm` include them, and the dry-run report's scan covers all of `state/<dry pass>/`.

The feed is a convenience: any failure to write it disables it for the rest of that turn and never fails the turn.
`watch` is read-only: it never takes the runner lock and never writes anything.
"""
from __future__ import annotations

import json, os, re, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO

from runner import paths

CURRENT = "current.json"
TOOL_MAX = 160                  # a tool call's argument summary
TEXT_MAX = 200                  # assistant text
SUBAGENT_TOOLS = ("Agent", "Task")      # Claude Code 2.1.281 calls it Agent (probe P3/P3b); Task is the old name
STOP_HINT = ("To stop the run: Ctrl-C in the runner's terminal (the step is left `interrupted`), then record it as "
             "a harness fault: `runner faults declare <pass> <arm> <step> <slug> --scope record` (ledgered "
             "as manual:<slug>), then resume. A declared stop fails a canary's no-harness-fault row: after one, run a "
             "fresh canary. A stop during setup (step 0) has no ledger entry (declare takes steps 1-7): rerun the "
             "setup. Ctrl-C here only stops watching.")

Redact = Callable[[str], str]
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def visible(text: str) -> str:
    """Every C0/C1 control character and DEL as a visible `\\xNN` (fix round 1, I-1): model text, tool inputs and
    arm file contents can carry ESC sequences, backspaces or OSC strings that would erase or rewrite what the
    owner's terminal shows. Applied when the feed is written AND when watch prints it."""
    return _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


# ---- pure: stream events -> feed lines ---------------------------------------------------------------------------

def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def tool_summary(name: str, inp: object) -> str:
    """`Bash: uv run pytest -q`, `Edit: src/x.py`, `Agent: <description>` — the one argument that says what a call
    does, else the first short string argument, else the argument names."""
    if not isinstance(inp, dict):
        return name
    key = {"Bash": "command", "Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path",
           "Read": "file_path", "NotebookEdit": "notebook_path", "Grep": "pattern", "Glob": "pattern",
           "WebFetch": "url", "WebSearch": "query", "Skill": "skill", "Agent": "description",
           "Task": "description"}.get(name)
    val = inp.get(key) if key else None
    if not isinstance(val, str):
        val = next((v for v in inp.values() if isinstance(v, str) and v.strip()), None)
    if val is None:
        return f"{name}: ({', '.join(sorted(map(str, inp)))})" if inp else name
    if name == "Grep" and isinstance(inp.get("path"), str):
        val = f"{val}  in {inp['path']}"
    return f"{name}: {val}"


@dataclass
class FeedState:
    """What formatting needs to remember across one turn's events: the subagent calls still open."""
    subagents: dict[str, str] = field(default_factory=dict)       # tool_use id -> description


def format_event(ev: object, st: FeedState) -> list[str]:
    """One stream-json event -> zero or more feed bodies (no timestamp, not yet redacted or trimmed; `Feed` does
    both). Only what the owner needs to see a turn going wrong: tool calls, assistant text, subagent start and
    stop, retries, tool errors, the result. Thinking, token accounting and allowed rate-limit ticks are dropped."""
    if not isinstance(ev, dict):
        return []
    t, sub = ev.get("type"), ev.get("subtype")
    pre = "[sub] " if ev.get("parent_tool_use_id") else ""
    if t == "system" and sub == "init":
        return [f"init: model {ev.get('model')}, session {str(ev.get('session_id') or '?')[:8]}"]
    if t == "system" and sub == "api_retry":
        return [f"api retry: attempt {ev.get('attempt')}, error {ev.get('error')}"]
    if t == "rate_limit_event":
        info = ev.get("rate_limit_info") or {}
        return [] if info.get("status") == "allowed" else [f"rate limit: {info.get('status')}"]
    if t == "bk_oversize_line":
        return [f"oversize stream line dropped ({ev.get('bytes')} bytes)"]
    if t == "result":
        outcome = "is_error" if ev.get("is_error") else "ok"
        cost = ev.get("total_cost_usd")
        dur = ev.get("duration_ms")
        bits = [f"result: {outcome} ({ev.get('subtype')})",
                f"cost ${float(cost):.4f}" if isinstance(cost, (int, float)) else "cost ?",
                f"{ev.get('num_turns')} model turns"]
        if isinstance(dur, (int, float)):
            bits.append(f"{dur / 1000:.0f}s")
        text = ev.get("result")
        return [", ".join(bits) + (f" — {_one_line(text)}" if isinstance(text, str) and text.strip() else "")]
    content = (ev.get("message") or {}).get("content") if isinstance(ev.get("message"), dict) else None
    if not isinstance(content, list):
        return []
    out: list[str] = []
    for c in content:
        if not isinstance(c, dict):
            continue
        if t == "assistant" and c.get("type") == "text" and str(c.get("text") or "").strip():
            out.append(f"{pre}text: {_one_line(c['text'])}")
        elif t == "assistant" and c.get("type") == "tool_use":
            name = str(c.get("name") or "?")
            if name in SUBAGENT_TOOLS:
                raw = c.get("input")
                inp: dict = raw if isinstance(raw, dict) else {}
                desc = str(inp.get("description") or "?")
                st.subagents[str(c.get("id"))] = desc
                kind = inp.get("subagent_type") or inp.get("model")
                out.append(f"{pre}subagent start: {desc}" + (f" ({kind})" if kind else ""))
            else:
                out.append(f"{pre}tool {tool_summary(name, c.get('input'))}")
        elif t == "user" and c.get("type") == "tool_result":
            tid = str(c.get("tool_use_id"))
            if tid in st.subagents:
                out.append(f"{pre}subagent done: {st.subagents.pop(tid)}")
            elif c.get("is_error"):
                body = c.get("content")
                if isinstance(body, list):
                    body = " ".join(str(b.get("text") or "") for b in body if isinstance(b, dict))
                out.append(f"{pre}tool error: {_one_line(str(body or ''))}")
    return out


def _limit_for(body: str) -> int:
    b = body[len("[sub] "):] if body.startswith("[sub] ") else body
    return TOOL_MAX if b.startswith("tool ") else TEXT_MAX


def run_label(p: paths.Paths, out_dir: Path) -> str:
    """`a` / `b` for a step's N.a / N.b evidence dir (`NN/a/…` / `NN/…`), `setup` for `00-setup`, else `-`."""
    try:
        parts = Path(out_dir).resolve().relative_to(p.results.resolve()).parts
    except ValueError:
        return "-"
    if not parts:
        return "-"
    if parts[0] == "00-setup":
        return "setup"
    if len(parts[0]) == 2 and parts[0].isdigit():
        return "a" if parts[1:2] == ("a",) else "b"
    return "-"


# ---- the writer (session.run_turn) -------------------------------------------------------------------------------

def _stamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S")


def _elapsed(secs: float) -> str:
    secs = max(0, int(secs))
    return f"{secs // 3600}:{secs % 3600 // 60:02d}:{secs % 60:02d}" if secs >= 3600 else \
        f"{secs // 60:02d}:{secs % 60:02d}"


class Feed:
    """One turn's live feed. `start()` creates the file and the `current.json` pointer; `event(line)` formats,
    redacts, trims, writes and flushes; `end(summary)` writes the last line and removes the pointer (only if it
    is still ours). Every write error disables the feed for the rest of the turn; nothing here raises into the
    turn (`start` returns False instead)."""

    def __init__(self, p: paths.Paths, *, step: int, run: str, stem: str, role: str, attempt: int, n: int,
                 evidence: Path, redact: Redact, clock: Callable[[], float] = time.time):
        self.p, self.redact, self.clock = p, redact, clock
        self.step, self.run, self.stem, self.role, self.attempt, self.n = step, run, stem, role, attempt, n
        self.evidence = evidence
        self.started = clock()
        started_s = datetime.fromtimestamp(self.started, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = p.live / f"{step:02d}-{run}-{stem}-{started_s}.log"
        self.turn_id = f"{step:02d}{run if run in ('a', 'b') else ''} {stem}"
        self.state = FeedState()
        self._fh: TextIO | None = None

    def start(self) -> bool:
        try:
            self.p.live.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            self._fh = os.fdopen(fd, "w", buffering=1, encoding="utf-8", errors="replace")
            self._write(f"turn start: {self.p.pass_}/{self.p.arm} step {self.step} run {self.run}, {self.role} "
                        f"attempt {self.attempt} turn {self.n}")
            rel = str(self.evidence)
            try:
                rel = str(Path(self.evidence).resolve().relative_to(paths.REPO_ROOT))
            except ValueError:
                pass
            ptr = {"file": self.path.name, "pid": os.getpid(), "started": self.started, "pass": self.p.pass_,
                   "arm": self.p.arm, "step": self.step, "run": self.run, "stem": self.stem, "role": self.role,
                   "attempt": self.attempt, "n": self.n, "evidence": rel}
            tmp = self.p.live / f".{CURRENT}.{os.getpid()}.tmp"
            tmp.write_text(json.dumps(ptr))
            os.replace(tmp, self.p.live / CURRENT)
            return True
        except Exception:                        # noqa: BLE001 -- a convenience feed never fails a turn
            self._close()
            return False

    def _write(self, body: str) -> None:
        if self._fh is None:
            return
        try:
            safe = _trim(visible(_one_line(self.redact(body))), _limit_for(body))
            now = self.clock()
            self._fh.write(f"{_stamp(now)} +{_elapsed(now - self.started)} [{self.turn_id}] {safe}\n")
            self._fh.flush()
        except Exception as e:                   # noqa: BLE001
            self._disable(e)

    def _disable(self, e: BaseException) -> None:
        """Stop writing, and say so in the pointer (fix round 1, m-1): a silent feed would look like a hung arm."""
        self._close()
        try:
            cur = self.p.live / CURRENT
            info = json.loads(cur.read_text())
            if info.get("file") == self.path.name:
                info["feed"] = f"disabled: {type(e).__name__}"
                tmp = self.p.live / f".{CURRENT}.{os.getpid()}.tmp"
                tmp.write_text(json.dumps(info))
                os.replace(tmp, cur)
        except Exception:                        # noqa: BLE001 -- best effort
            pass

    def event(self, line: str) -> None:
        if self._fh is None:
            return
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return
        try:
            bodies = format_event(ev, self.state)
        except Exception:                        # noqa: BLE001 -- an unexpected event shape: skip it
            return
        for b in bodies:
            self._write(b)

    def end(self, summary: str) -> None:
        self._write(f"turn end: {summary}")
        self._close()
        try:
            cur = self.p.live / CURRENT
            if json.loads(cur.read_text()).get("file") == self.path.name:
                cur.unlink()
        except Exception:                        # noqa: BLE001
            pass

    def _close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:                    # noqa: BLE001
                pass
            self._fh = None


# ---- the reader (`runner watch`) ---------------------------------------------------------------------------------

def pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(frozen=True)
class Current:
    path: Path
    info: dict


def find_current(pass_: str | None = None, arm: str | None = None, *,
                 alive: Callable[[object], bool] = pid_alive) -> Current | None:
    """The running turn: among `state/<pass>/<arm>/live/current.json` (filtered by pass/arm), those whose runner
    pid is alive and whose feed exists, the most recently started. Reads only; never follows a link."""
    root = paths.STATE
    if os.path.islink(root) or not root.is_dir():
        return None
    best: Current | None = None
    for ptr in root.glob(f"{pass_ or '*'}/{arm or '*'}/live/{CURRENT}"):
        if any(os.path.islink(x) for x in (ptr, ptr.parent, ptr.parent.parent, ptr.parent.parent.parent)):
            continue
        try:
            info = json.loads(ptr.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(info, dict) or not alive(info.get("pid")):
            continue
        name = str(info.get("file") or "")
        f = ptr.parent / name
        if "/" in name or not name or os.path.islink(f) or not f.is_file():
            continue
        if best is None or float(info.get("started") or 0) > float(best.info.get("started") or 0):
            best = Current(f, info)
    return best


def header(c: Current, now: float) -> str:
    i = c.info
    return visible(f"=== {i.get('pass')}/{i.get('arm')}  step {i.get('step')}  run {i.get('run')}  "
                   f"{i.get('role')} attempt {i.get('attempt')} turn {i.get('n')}  "
                   f"elapsed {_elapsed(now - float(i.get('started') or now))}  (evidence: {i.get('evidence')}) ===")


def follow(out: TextIO, pass_: str | None = None, arm: str | None = None, *, poll: float = 0.5,
           alive: Callable[[object], bool] = pid_alive, sleep: Callable[[float], None] = time.sleep,
           clock: Callable[[], float] = time.time, until: Callable[[], bool] | None = None) -> None:
    """tail -f the running turn's feed; when the pointer names a new turn, finish the old feed and switch; with no
    running turn, say so once and wait. Returns when `until()` is true (tests); the CLI ends it with Ctrl-C."""
    out.write(f"runner watch: {pass_ or 'any pass'}/{arm or 'any arm'}. {STOP_HINT}\n")
    out.flush()
    fh, following, buf, waiting, disabled_said = None, None, "", False, False

    def drain() -> None:
        nonlocal buf
        if fh is None:
            return
        chunk = fh.read()
        if chunk:
            buf += chunk
            *lines, buf = buf.split("\n")
            for ln in lines:
                out.write(visible(ln) + "\n")
            out.flush()

    while until is None or not until():
        cur = find_current(pass_, arm, alive=alive)
        if fh is not None and (cur is None or cur.path != following):
            drain()
            if buf:
                out.write(visible(buf) + "\n")
                buf = ""
            fh.close()
            fh, following = None, None
            out.write("--- turn ended ---\n")
            out.flush()
        if cur is not None and fh is None:
            try:
                fd = os.open(cur.path, os.O_RDONLY | os.O_NOFOLLOW)
                fh = os.fdopen(fd, "r", encoding="utf-8", errors="replace")
                following, waiting, disabled_said = cur.path, False, False
                out.write(header(cur, clock()) + "\n")
                out.flush()
            except OSError:
                fh = None
        if fh is not None:
            drain()
            why = cur.info.get("feed") if cur is not None else None
            if why and not disabled_said:
                out.write(visible(f"!!! live feed disabled ({str(why).removeprefix('disabled: ')}): this view stops "
                                  f"updating here, but the turn itself is still running (evidence: "
                                  f"{cur.info.get('evidence') if cur else '?'})") + "\n")
                out.flush()
                disabled_said = True
        elif not waiting:
            out.write("no running turn; waiting for one to start (Ctrl-C to stop watching)\n")
            out.flush()
            waiting = True
        sleep(poll)
    if fh is not None:
        fh.close()
