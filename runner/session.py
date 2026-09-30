"""One Claude turn in one container: supervision, stream + stderr capture, outcome (design §6; spike B Q5/Q8).

The container runs `bk-claude-turn /inbox/msg.md` (base image), which reads the OAuth token from stdin line 1
into fd 3 and runs `claude -p <msg> --model <pinned> --output-format stream-json --verbose ...`.

Outcome rules (spike B):
  ok          a `result` event with `is_error == false`
  is_error    a `result` event with `is_error == true`, whatever its subtype (401s come back as "success")
  no_result   the process ended without a `result` (a SIGTERM'd claude emits none)
  auth_failed a `system/api_retry` with `error == "authentication_failed"` (the container is stopped at once),
              or an `is_error` result whose stripped text STARTS WITH one of Claude Code's own auth messages
              (AUTH_FAILURE_SHAPES) on a turn that did no work (no tool_use, cost 0 or absent): a credential
              fault is the harness's, never charged to the arm — but an arm's own failure that merely
              mentions a 401 stays `is_error` (fix round 2)
  timeout     over `timeout_s` (the caller passes `limits.turn_seconds`); the container is stopped
"""
from __future__ import annotations
import asyncio, gzip, json, os, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Iterable, Literal
from runner import docker, transcripts
from runner.credentials import Credential
from runner.docker import Mount, RunSpec
from runner.config import load_pins

Outcome = Literal["ok", "is_error", "no_result", "timeout", "auth_failed"]
ROLES = ("arm", "po", "teammate", "setup", "probe")
STREAM_LINE_LIMIT = 64 * 1024 * 1024        # asyncio's 64 KiB default breaks on real stream-json lines (spike B)
POST_STOP_DRAIN_S = 90                      # docker stop grace (30 s) + rm, with margin
OVERSIZE_MARKER = "bk_oversize_line"        # written to the stream in place of a line over the reader limit

# How Claude Code's own credential-failure result texts BEGIN (fix round 2: anchored prefixes, never mid-text
# substrings). Used only for an `is_error` result on a turn that did no work (see Parsed.outcome).
#   "Not logged in"          spike FINDINGS.md Evidence 2, verbatim: "Not logged in · Please run /login"
#   "Failed to authenticate" spike FINDINGS.md Q3/Q7, verbatim: "Failed to authenticate. API Error: 401 ..."
#   "Invalid API key"        Claude Code's bad-key message ("Invalid API key · ..."); [UNVERIFIED] in the spike
AUTH_FAILURE_SHAPES = ("Not logged in", "Failed to authenticate", "Invalid API key")


@dataclass
class Parsed:
    session_id: str | None = None
    init: dict = field(default_factory=dict)
    result: dict | None = None
    retries: list[dict] = field(default_factory=list)
    auth_failed: bool = False
    tool_uses: int = 0              # assistant tool_use blocks seen: the turn did work

    @property
    def outcome(self) -> Outcome:
        if self.auth_failed:
            return "auth_failed"
        if self.result is None:
            return "no_result"
        if not self.result.get("is_error"):
            return "ok"
        text = str(self.result.get("result") or "").strip()
        no_work = self.tool_uses == 0 and not self.result.get("total_cost_usd")
        return "auth_failed" if no_work and text.startswith(AUTH_FAILURE_SHAPES) else "is_error"

    @property
    def final_text(self) -> str:
        return (self.result or {}).get("result") or ""

    @property
    def cost_usd(self) -> float:
        return float((self.result or {}).get("total_cost_usd") or 0.0)


def feed(p: Parsed, line: str) -> None:
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return                                   # a truncated last line (timed-out turn) is not fatal
    if not isinstance(ev, dict):
        return
    t, st = ev.get("type"), ev.get("subtype")
    if t == "system" and st == "init":
        p.init, p.session_id = ev, ev.get("session_id")
    elif t == "system" and st == "api_retry":
        p.retries.append(ev)
        if ev.get("error") == "authentication_failed":
            p.auth_failed = True
    elif t == "result":
        p.result = ev
    elif t == "assistant":
        content = (ev.get("message") or {}).get("content") or []
        if isinstance(content, list):
            p.tool_uses += sum(1 for c in content if isinstance(c, dict) and c.get("type") == "tool_use")


def parse_stream(lines: Iterable[str]) -> Parsed:
    """Pure: the stream-json lines of one turn → what the runner needs from them."""
    p = Parsed()
    for line in lines:
        feed(p, line)
    return p


@dataclass(frozen=True)
class Turn:
    pass_: str
    arm: str
    step: int
    attempt: int
    n: int
    image: str
    message: str
    env: dict[str, str]
    mounts: list[Mount]
    network: str
    proxy: bool
    workdir: str
    inbox_dir: Path                 # the role's OWN host inbox (Paths.inbox(role)); only one file is mounted
    role: str = "arm"               # arm | po | teammate | setup | probe
    dry: bool = False
    config_dir: Path | None = None  # host path of the session's CLAUDE_CONFIG_DIR (post-turn credential check)


@dataclass
class TurnResult:
    session_id: str | None
    outcome: Outcome
    final_text: str
    init: dict
    result: dict | None
    cost_usd: float
    usage: dict
    model_usage: dict
    wall_seconds: float
    retries: list[dict]
    stream_path: Path | None
    stderr_path: Path | None = None
    permission_denials: list[dict] = field(default_factory=list)
    credential_files: list[str] = field(default_factory=list)
    oom_killed: bool = False        # A5: the session container was killed for memory (OOMKilled, or exit 137)
    exit_code: int | None = None    # the session container's exit code, when it exited by itself


def stem(t: Turn) -> str:
    """File/container stem: role, attempt and turn number. Unique only within one out_dir (the caller gives
    every step its own out_dir; the container name adds pass, arm and step). The role inbox is shared across
    steps, so a later step's `<stem>.md` there replaces an earlier one — harmless, as it is only the mount
    source during its own turn; the record of the prompt is `out_dir/turns/<stem>.prompt.md`."""
    return f"{t.role}-a{t.attempt}-{t.n:03d}"


def container_name(t: Turn) -> str:
    return f"bk-{t.pass_}-{t.arm}-{t.step:02d}-{stem(t)}"


def credential_files(config_dir: Path | None, cred: Credential, since: float) -> list[str]:
    """Files under config_dir changed during the turn that contain the token, and any .credentials.json (S-3).
    The scan lives in runner.secrets (the only reader of the raw token, Task 21); see its docstring."""
    from runner import secrets
    return secrets.credential_files(config_dir, cred, since)


async def read_lines(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Lines from `reader`; a line longer than the reader's limit is discarded and replaced by one
    `{"type": "bk_oversize_line", "bytes": N}` marker line, and reading continues (fix round 1, item 3).
    A final line without a newline (a stopped turn) is delivered as it is."""
    while True:
        try:
            yield await reader.readuntil(b"\n")
        except asyncio.IncompleteReadError as e:
            if e.partial:
                yield e.partial
            return
        except asyncio.LimitOverrunError as e:
            dropped, consumed = 0, e.consumed
            while True:
                await reader.readexactly(consumed)
                dropped += consumed
                try:
                    dropped += len(await reader.readuntil(b"\n"))
                    break
                except asyncio.IncompleteReadError as e2:
                    dropped += len(e2.partial)
                    break
                except asyncio.LimitOverrunError as e2:
                    consumed = e2.consumed
            yield (json.dumps({"type": OVERSIZE_MARKER, "bytes": dropped}) + "\n").encode()


def _spec(t: Turn) -> RunSpec:
    msg_file = t.inbox_dir / f"{stem(t)}.md"
    # Only this turn's message file is mounted, read-only — never the inbox directory (review C-12).
    return RunSpec(name=container_name(t), image=t.image, label=f"bakeoff.run={t.pass_}/{t.arm}",
                   network=t.network, mounts=[*t.mounts, Mount(msg_file, "/inbox/msg.md", True)], env=t.env,
                   workdir=t.workdir, cmd=["bk-claude-turn", "/inbox/msg.md"], stdin=True,
                   limits=load_pins().limits, proxy=t.proxy, remove=False)   # inspected, then removed (A5)


async def _run(t: Turn, cred: Credential, stream_path: Path, stderr_path: Path,
               timeout_s: float) -> tuple[Parsed, str, tuple[bool, int | None]]:
    spec = _spec(t)
    proc = await asyncio.create_subprocess_exec(*docker.run_argv(spec), stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                start_new_session=True, limit=STREAM_LINE_LIMIT)
    parsed, how, err_task, state = Parsed(), "exited", None, (False, None)
    try:
        with gzip.open(stream_path, "wt") as out, gzip.open(stderr_path, "wb") as err:
            async def drain_stderr():                              # review C-9: never blocks the container
                while chunk := await proc.stderr.read(65536):
                    err.write(chunk)

            async def pump(stop_on_auth: bool):
                async for raw in read_lines(proc.stdout):
                    line = raw.decode(errors="replace")
                    out.write(line); feed(parsed, line)
                    if stop_on_auth and parsed.auth_failed:
                        return

            err_task = asyncio.create_task(drain_stderr())
            try:
                proc.stdin.write(cred.payload())
                await proc.stdin.drain()
                proc.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass                                               # docker failed to start: stderr says why
            try:
                await asyncio.wait_for(pump(stop_on_auth=True), timeout=timeout_s)
                if parsed.auth_failed:
                    how = "auth_failed"                            # don't sit through the retry schedule
            except asyncio.TimeoutError:
                how = "timeout"
            if how != "exited":
                await asyncio.to_thread(docker.stop, spec.name)    # stderr keeps draining meanwhile
            try:                                                   # keep what was already written (evidence)
                await asyncio.wait_for(pump(stop_on_auth=False), timeout=POST_STOP_DRAIN_S)
                await asyncio.wait_for(asyncio.shield(err_task), timeout=POST_STOP_DRAIN_S)
                await asyncio.wait_for(proc.wait(), timeout=POST_STOP_DRAIN_S)
            except asyncio.TimeoutError:
                # The CLI has not exited: the container may still be alive (fix round 1, item 2).
                await asyncio.to_thread(docker.stop, spec.name)
                proc.kill()
                await proc.wait()
        if how == "exited":                                        # A5: why did it end? (kept until now)
            oom, code = await asyncio.to_thread(docker.exit_state, spec.name)
            code = code if code is not None else proc.returncode
            state = (oom or code == 137, code)
    finally:
        if err_task is not None and not err_task.done():
            err_task.cancel()
        if proc.returncode is None:
            # An exception or cancellation mid-turn: never leave the container behind.
            await asyncio.to_thread(docker.stop, spec.name)
            proc.kill()
            await proc.wait()
        await asyncio.to_thread(docker.remove, spec.name)          # not --rm: removed once inspected
    return parsed, how, state


def run_turn(t: Turn, cred: Credential, out_dir: Path, timeout_s: float) -> TurnResult:
    """Run one turn. Writes out_dir/turns/<stem>.prompt.md, .stream.jsonl.gz and .stderr.gz."""
    cred.check_turn(t.dry)                                     # review C-14: before anything is written
    if t.role not in ROLES:
        raise ValueError(f"unknown role {t.role!r}; expected one of {ROLES}")
    turns = out_dir / "turns"
    turns.mkdir(parents=True, exist_ok=True)
    t.inbox_dir.mkdir(parents=True, exist_ok=True)
    (t.inbox_dir / f"{stem(t)}.md").write_text(t.message)
    (turns / f"{stem(t)}.prompt.md").write_text(t.message)
    stream = turns / f"{stem(t)}.stream.jsonl.gz"
    stderr = turns / f"{stem(t)}.stderr.gz"
    wall0, start = time.time(), time.monotonic()
    parsed, how, (oom, code) = asyncio.run(_run(t, cred, stream, stderr, timeout_s))
    wall = time.monotonic() - start
    outcome: Outcome = "timeout" if how == "timeout" else parsed.outcome
    r = parsed.result or {}
    return TurnResult(parsed.session_id, outcome, parsed.final_text, parsed.init, parsed.result, parsed.cost_usd,
                      r.get("usage", {}), r.get("modelUsage", {}), wall, parsed.retries,
                      stream, stderr, list(r.get("permission_denials") or []),
                      credential_files(t.config_dir, cred, wall0 - 1), oom, code)
